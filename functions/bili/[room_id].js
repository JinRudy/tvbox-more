/**
 * Cloudflare Pages Function: Bilibili 动态直播流解析与切片代理 (/bili/:room_id)
 * 作用: 实时换取 B 站合法短期 Token 与 m3u8 流，伪造 Referer 转发，彻底解决 403 与时效性问题
 */

export async function onRequest(context) {
  const { request, params, env } = context;
  const requestUrl = new URL(request.url);
  const roomId = params.room_id;

  // 1. 处理 CORS
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

  // 2. 如果是 TS 切片转发请求 (?ts=https://...)
  const tsTarget = requestUrl.searchParams.get("ts");
  if (tsTarget) {
    try {
      const tsResp = await fetch(tsTarget, {
        method: request.method,
        headers: {
          "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
          "Referer": "https://live.bilibili.com/",
        },
      });
      const tsHeaders = new Headers(tsResp.headers);
      tsHeaders.set("Access-Control-Allow-Origin", "*");
      return new Response(tsResp.body, {
        status: tsResp.status,
        headers: tsHeaders,
      });
    } catch (e) {
      return new Response("TS Fetch Error: " + e.message, { status: 502 });
    }
  }

  // 3. 正常请求：动态解析 B 站直播房间流
  if (!roomId) {
    return new Response("Missing room_id in path: /bili/:room_id", { status: 400 });
  }

  const apiUrl = `https://api.live.bilibili.com/room/v1/Room/playUrl?cid=${encodeURIComponent(roomId)}&quality=4&platform=h5`;

  const apiHeaders = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
    "Referer": `https://live.bilibili.com/${roomId}`,
  };

  if (env.BILI_COOKIE) {
    apiHeaders["Cookie"] = env.BILI_COOKIE;
  }

  let m3u8Url = "";
  try {
    const apiResp = await fetch(apiUrl, { headers: apiHeaders });
    const apiData = await apiResp.json();
    if (apiData.code === 0 && apiData.data && apiData.data.durl && apiData.data.durl.length > 0) {
      m3u8Url = apiData.data.durl[0].url;
    }
  } catch (err) {
    return new Response("Bilibili API Error: " + err.message, { status: 502 });
  }

  if (!m3u8Url) {
    return new Response(`Bilibili Room ${roomId} is offline or unavailable`, { status: 404 });
  }

  // 4. 拉取真实的 m3u8 内容并重写切片链接
  try {
    const m3u8Resp = await fetch(m3u8Url, {
      headers: {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
        "Referer": "https://live.bilibili.com/",
      },
    });

    if (m3u8Resp.status !== 200) {
      return new Response("Failed to fetch m3u8 from upstream", { status: m3u8Resp.status });
    }

    const m3u8Text = await m3u8Resp.text();
    const lines = m3u8Text.split("\n");
    const rewrittenLines = [];

    for (let line of lines) {
      let trimmed = line.trim();
      if (!trimmed) {
        rewrittenLines.push(line);
        continue;
      }

      if (trimmed.startsWith("#")) {
        rewrittenLines.push(line);
        continue;
      }

      // 相对切片补全为绝对路径，并包装为通过当前 Function 的 ?ts= 参数代理转发
      try {
        const fullTsUrl = new URL(trimmed, m3u8Url).href;
        const proxiedTsUrl = `${requestUrl.origin}${requestUrl.pathname}?ts=${encodeURIComponent(fullTsUrl)}`;
        rewrittenLines.push(proxiedTsUrl);
      } catch (e) {
        rewrittenLines.push(trimmed);
      }
    }

    return new Response(rewrittenLines.join("\n"), {
      status: 200,
      headers: {
        "Content-Type": "application/vnd.apple.mpegurl; charset=utf-8",
        "Access-Control-Allow-Origin": "*",
        "Cache-Control": "no-cache, no-store, must-revalidate",
      },
    });
  } catch (e) {
    return new Response("M3U8 Parse Error: " + e.message, { status: 502 });
  }
}
