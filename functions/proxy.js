/**
 * Cloudflare Pages Function: M3U8 流媒体反向代理与切片重写器 (/proxy)
 * 作用: 为国内无法科学上网的电视盒子提供无缝海外电视频道直连转发
 */

export async function onRequest(context) {
  const { request } = context;
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

  // 2. 从 query 中提取目标 URL
  let targetUrlStr = requestUrl.searchParams.get("url");
  if (!targetUrlStr) {
    return new Response(
      "M3U8 Streaming Proxy is Running!\nUsage: /proxy?url=https://example.com/live.m3u8",
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

      // 如果是具体的分片 URL 或子 m3u8，重写为通过当前 Pages Function 代理转发
      try {
        const absoluteSliceUrl = new URL(trimmed, targetUrl.href).href;
        const proxiedSliceUrl = `${requestUrl.origin}${requestUrl.pathname}?url=${encodeURIComponent(absoluteSliceUrl)}`;
        rewrittenLines.push(proxiedSliceUrl);
      } catch (err) {
        rewrittenLines.push(trimmed);
      }
    }

    const modifiedContent = rewrittenLines.join("\n");
    const responseHeaders = new Headers(response.headers);
    responseHeaders.set("Content-Type", "application/vnd.apple.mpegurl; charset=utf-8");
    responseHeaders.set("Access-Control-Allow-Origin", "*");

    return new Response(modifiedContent, {
      status: response.status,
      headers: responseHeaders,
    });
  }

  // 5. 如果是切片 (.ts) 或其他音视频二进制数据，直接流式透传转发
  const binaryHeaders = new Headers(response.headers);
  binaryHeaders.set("Access-Control-Allow-Origin", "*");
  return new Response(response.body, {
    status: response.status,
    headers: binaryHeaders,
  });
}
