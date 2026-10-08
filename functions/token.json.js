/**
 * Cloudflare Pages Function: 安全云端网盘凭据分发 (/token.json)
 * 作用: 为全家电视提供免扫码 4K 网盘凭据，完全隔离在 Cloudflare 环境变量中，绝不泄漏至 GitHub
 */

export async function onRequest(context) {
  const { request, env } = context;
  const requestUrl = new URL(request.url);

  // 1. CORS 支持
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

  // 2. 鉴权校验 (若在 Cloudflare 后台配置了 AUTH_KEY，则校验 ?key= 参数)
  const expectedKey = env.AUTH_KEY || "";
  const clientKey = requestUrl.searchParams.get("key") || "";

  if (expectedKey && clientKey !== expectedKey) {
    return new Response(
      JSON.stringify({ error: "Unauthorized: Invalid or missing secret key" }, null, 2),
      {
        status: 403,
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "Access-Control-Allow-Origin": "*",
        },
      }
    );
  }

  // 3. 从 Cloudflare 加密环境变量中取出凭据构建载荷
  const tokenPayload = {
    token: env.ALI_TOKEN || "",
    open_token: env.ALI_OPEN_TOKEN || "",
    quark_cookie: env.QUARK_COOKIE || "",
    thread_limit: parseInt(env.THREAD_LIMIT || "8", 10),
    is_vip: true,
  };

  return new Response(JSON.stringify(tokenPayload, null, 2), {
    status: 200,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Access-Control-Allow-Origin": "*",
      "Cache-Control": "no-store, no-cache, must-revalidate",
    },
  });
}
