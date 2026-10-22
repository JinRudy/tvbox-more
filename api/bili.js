const https = require("https");
const { URL } = require("url");

function fetchHttps(urlStr, headers = {}, timeoutMs = 5000) {
  return new Promise((resolve, reject) => {
    const u = new URL(urlStr);
    const options = {
      protocol: u.protocol,
      hostname: u.hostname,
      port: u.port || 443,
      path: u.pathname + u.search,
      method: "GET",
      headers: {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
        ...headers,
      },
      timeout: timeoutMs,
    };

    const req = https.request(options, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        const nextUrl = new URL(res.headers.location, urlStr).href;
        return resolve(fetchHttps(nextUrl, headers, timeoutMs));
      }

      const chunks = [];
      res.on("data", (chunk) => chunks.push(chunk));
      res.on("end", () => {
        resolve({
          statusCode: res.statusCode,
          headers: res.headers,
          body: Buffer.concat(chunks),
        });
      });
    });

    req.on("error", (err) => reject(err));
    req.on("timeout", () => {
      req.destroy();
      reject(new Error("Request Timeout after " + timeoutMs + "ms"));
    });
    req.end();
  });
}

module.exports = async (req, res) => {
  const { room_id } = req.query;

  // 1. CORS
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "*");

  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  // 2. 动态向 B 站 API 换取当期有效的真实直播流
  const roomId = room_id || "6";
  const apiUrl = `https://api.live.bilibili.com/room/v1/Room/playUrl?cid=${encodeURIComponent(roomId)}&quality=4&platform=h5`;

  try {
    const apiResp = await fetchHttps(apiUrl, {
      "Referer": `https://live.bilibili.com/${roomId}`,
    }, 4000);

    const apiData = JSON.parse(apiResp.body.toString("utf-8"));
    if (apiData.code === 0 && apiData.data && apiData.data.durl && apiData.data.durl.length > 0) {
      let liveUrl = apiData.data.durl[0].url;

      // 如果返回的是海外 ov-gotcha 域名，替换为国内通用的 cn-gotcha 域名，确保国内电视秒开
      if (liveUrl.includes("-ov-gotcha")) {
        liveUrl = liveUrl.replace(/-ov-gotcha\d+/, "-cn-gotcha104");
      }

      console.log(`[BiliProxy] Success: 302 Redirecting Room ${roomId} to live stream`);
      res.setHeader("Location", liveUrl);
      res.setHeader("Cache-Control", "no-cache, no-store, must-revalidate");
      return res.status(302).end();
    } else {
      console.warn(`[BiliProxy] Room ${roomId} is offline or error:`, apiData);
      return res.status(404).send(`Room ${roomId} is offline`);
    }
  } catch (err) {
    console.error("[BiliProxy] API Failed:", err.message);
    return res.status(502).send("API Failed: " + err.message);
  }
};
