/**
 * Cloudflare Pages Middleware: 全站与多仓私有化鉴权网关
 * 
 * 作用:
 * 1. 拦截未经授权的公网陌生人访问 (当在 Cloudflare 配置了 AUTH_KEY 时，必须提供合法 ?key= 才能访问多仓与主仓)
 * 2. 自动在多仓 (tvboxmuti.json) 中为自建主仓 (tvboxvod.json) 继承并注入当前合法 ?key=，使电视端零感知平滑流转
 */

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);

  // 1. CORS 跨域放行
  if (request.method === "OPTIONS") {
    return new Response(null, {
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
        "Access-Control-Allow-Headers": "*",
        "Access-Control-Max-Age": "86400",
      },
    });
  }

  // 2. 检查环境变量是否开启了整仓私有化鉴权 (AUTH_KEY)
  const expectedKey = (env.AUTH_KEY || "").trim();
  const clientKey = (url.searchParams.get("key") || "").trim();

  // 若设置了 AUTH_KEY，且访问的是核心配置 (.json)，执行私有安全门禁
  const isProtectedPath = url.pathname.endsWith(".json") || url.pathname === "/" || url.pathname === "";

  if (expectedKey && isProtectedPath) {
    if (clientKey !== expectedKey) {
      return new Response(
        JSON.stringify(
          {
            code: 403,
            error: "Unauthorized: Private TVBox Repository. Please provide a valid ?key= parameter in your TVBox configuration.",
          },
          null,
          2
        ),
        {
          status: 403,
          headers: {
            "Content-Type": "application/json; charset=utf-8",
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "no-store, no-cache, must-revalidate",
          },
        }
      );
    }
  }

  // 3. 鉴权通过或未开启保护，继续获取上游静态文件
  const response = await context.next();

  // 4. 若请求的是多仓配置 (tvboxmuti.json)，且开启了鉴权，自动将当前 key 继承注入给自建主仓
  if (expectedKey && clientKey === expectedKey && url.pathname.includes("tvboxmuti.json") && response.ok) {
    try {
      const mutiData = await response.json();
      if (Array.isArray(mutiData.urls)) {
        mutiData.urls = mutiData.urls.map((item) => {
          // 如果是本站的自建主仓，自动附加上 ?key=，实现电视端零操作无缝切换
          if (item.url && item.url.includes("tvboxvod.json")) {
            const separator = item.url.includes("?") ? "&" : "?";
            return {
              ...item,
              url: `${item.url}${separator}key=${encodeURIComponent(clientKey)}`,
            };
          }
          return item;
        });
      }

      return new Response(JSON.stringify(mutiData, null, 2), {
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "Access-Control-Allow-Origin": "*",
          "Cache-Control": "no-store, no-cache, must-revalidate",
        },
      });
    } catch (err) {
      // 解析失败降级返回原响应
      return response;
    }
  }

  return response;
}
