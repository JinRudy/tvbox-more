/**
 * Cloudflare Worker: M3U8 流媒体反向代理与切片重写器
 * 作用: 为国内无法科学上网的电视盒子提供无缝海外电视频道直连转发
 * 部署路由建议: tvbox.wushui.fun/proxy* 或 stream.wushui.fun/*
 */

export default {
  async fetch(request, env, ctx) {
    const requestUrl = new URL(request.url);

    // 1. 处理 CORS 跨域预检请求
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

    // 2. 处理安全云端网盘凭据分发 (/token.json)
    // 凭据完全存放在 Cloudflare Worker 内部环境变量(Secrets)，GitHub 仓库不留任何痕迹
    if (requestUrl.pathname === "/token.json") {
      const expectedKey = env.AUTH_KEY || "";
      const clientKey = requestUrl.searchParams.get("key") || "";

      if (expectedKey && clientKey !== expectedKey) {
        return new Response(JSON.stringify({ error: "Unauthorized: Invalid key" }), {
          status: 403,
          headers: { "Content-Type": "application/json; charset=utf-8", "Access-Control-Allow-Origin": "*" }
        });
      }

      const tokenPayload = {
        token: env.ALI_TOKEN || "",
        open_token: env.ALI_OPEN_TOKEN || "",
        quark_cookie: env.QUARK_COOKIE || "",
        thread_limit: parseInt(env.THREAD_LIMIT || "8", 10),
        is_vip: true
      };

      return new Response(JSON.stringify(tokenPayload, null, 2), {
        status: 200,
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "Access-Control-Allow-Origin": "*",
          "Cache-Control": "no-store, no-cache, must-revalidate"
        }
      });
    }

    // 3. 从 query 中提取目标 URL (M3U8 反向代理)
    let targetUrlStr = requestUrl.searchParams.get("url");
    if (!targetUrlStr) {
      return new Response(
        "TVBox Cloudflare Service is Running!\nUsage:\n- Stream Proxy: /proxy?url=https://example.com/live.m3u8\n- Safe Token: /token.json",
        {
          status: 200,
          headers: { "Content-Type": "text/plain; charset=utf-8" },
        }
      );
    }

    let targetUrl;
    try {
      targetUrl = new URL(targetUrlStr);
    } catch (e) {
      return new Response("Invalid Target URL: " + targetUrlStr, { status: 400 });
    }

    // 3. 构建向海外目标源的代理请求
    const newHeaders = new Headers(request.headers);
    newHeaders.set("Host", targetUrl.host);
    newHeaders.set("Referer", targetUrl.origin);
    newHeaders.set(
      "User-Agent",
      request.headers.get("User-Agent") || "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    );
    newHeaders.delete("CF-Connecting-IP");
    newHeaders.delete("CF-Ray");
    newHeaders.delete("CF-IPCountry");

    let response;
    try {
      response = await fetch(targetUrl.href, {
        method: request.method,
        headers: newHeaders,
        redirect: "follow",
      });
    } catch (err) {
      return new Response("Fetch Error: " + err.message, { status: 502 });
    }

    const contentType = response.headers.get("content-type") || "";
    const isM3U8 =
      targetUrl.pathname.endsWith(".m3u8") ||
      contentType.includes("mpegurl") ||
      contentType.includes("application/x-mpegURL");

    // 4. 如果是 M3U8 播放列表，逐行重写内部切片 (.ts) 和子播放列表地址
    if (isM3U8) {
      const text = await response.text();
      const lines = text.split("\n");
      const rewrittenLines = [];

      for (let line of lines) {
        let trimmed = line.trim();
        if (!trimmed) {
          rewrittenLines.push(line);
          continue;
        }

        // 处理 EXT-X-KEY 中的加密密钥 URI="..."
        if (trimmed.startsWith("#EXT-X-KEY:") && trimmed.includes('URI="')) {
          line = line.replace(/URI="([^"]+)"/, (match, keyUri) => {
            try {
              const fullKeyUrl = new URL(keyUri, targetUrl.href).href;
              const proxiedKeyUrl = `${requestUrl.origin}${requestUrl.pathname}?url=${encodeURIComponent(fullKeyUrl)}`;
              return `URI="${proxiedKeyUrl}"`;
            } catch (e) {
              return match;
            }
          });
          rewrittenLines.push(line);
          continue;
        }

        // 如果是注释或标签，原样保留
        if (trimmed.startsWith("#")) {
          rewrittenLines.push(line);
          continue;
        }

        // 如果是具体的分片 URL 或子 m3u8，重写为通过当前 Worker 代理转发
        try {
          const absoluteSliceUrl = new URL(trimmed, targetUrl.href).href;
          const proxiedSliceUrl = `${requestUrl.origin}${requestUrl.pathname}?url=${encodeURIComponent(absoluteSliceUrl)}`;
          rewrittenLines.push(proxiedSliceUrl);
        } catch (e) {
          rewrittenLines.push(line);
        }
      }

      return new Response(rewrittenLines.join("\n"), {
        status: response.status,
        headers: {
          "Content-Type": "application/vnd.apple.mpegurl; charset=utf-8",
          "Access-Control-Allow-Origin": "*",
          "Cache-Control": "no-cache, no-store, must-revalidate",
        },
      });
    }

    // 5. 如果是视频切片 (.ts / .aac) 或普通二进制数据，直接流式透传
    const responseHeaders = new Headers(response.headers);
    responseHeaders.set("Access-Control-Allow-Origin", "*");
    responseHeaders.set("Access-Control-Allow-Headers", "*");

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    });
  },
};
