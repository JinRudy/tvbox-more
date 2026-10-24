module.exports = async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "*");

  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  const { room_id } = req.query;
  const rawId = (room_id || "6").trim();
  const inputId = rawId.replace(/\.(m3u8|flv)$/i, "");

  try {
    // 1. 自动转换短号为真实长号 room_id 并检查开播状态
    const initUrl = `https://api.live.bilibili.com/room/v1/Room/room_init?id=${encodeURIComponent(inputId)}`;
    const initResp = await fetch(initUrl, {
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": `https://live.bilibili.com/${inputId}`,
      },
      signal: AbortSignal.timeout(5000),
    });

    const initData = await initResp.json();
    if (initData.code !== 0 || !initData.data?.room_id) {
      console.warn(`[BiliProxy] Room ${inputId} not found:`, initData?.message);
      return res.status(404).send(`Room ${inputId} not found`);
    }

    const realRoomId = initData.data.room_id;
    const isLive = initData.data.live_status === 1;

    if (!isLive) {
      console.warn(`[BiliProxy] Room ${inputId} (real: ${realRoomId}) is offline`);
      return res.status(404).send(`Room ${inputId} is currently offline`);
    }

    // 2. 调用 getRoomPlayInfo 动态获取当期超清直播流 (优先 HLS/m3u8，适配全平台 TVBox/ExoPlayer 硬解)
    const apiUrl = `https://api.live.bilibili.com/xlive/web-room/v2/index/getRoomPlayInfo?room_id=${encodeURIComponent(realRoomId)}&protocol=0,1&format=0,1,2&codec=0,1&qn=10000&platform=web`;
    const apiResp = await fetch(apiUrl, {
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": `https://live.bilibili.com/${realRoomId}`,
      },
      signal: AbortSignal.timeout(5000),
    });

    const apiData = await apiResp.json();
    if (apiData.code === 0 && apiData.data?.playurl_info?.playurl?.stream) {
      const streams = apiData.data.playurl_info.playurl.stream;
      
      let selectedUrl = "";

      // 优先方案：提取 HLS (http_hls) -> TS 切片 -> AVC/H.264 编码 (电视端 TVBox ExoPlayer 系统硬解最佳)
      const hlsStream = streams.find((s) => s.protocol_name === "http_hls");
      if (hlsStream && Array.isArray(hlsStream.format)) {
        const tsFormat = hlsStream.format.find((f) => f.format_name === "ts") || hlsStream.format[0];
        if (tsFormat && Array.isArray(tsFormat.codec) && tsFormat.codec.length > 0) {
          const avcCodec = tsFormat.codec.find((c) => c.codec_name === "avc") || tsFormat.codec[0];
          if (avcCodec && Array.isArray(avcCodec.url_info) && avcCodec.url_info.length > 0) {
            const urlInfo = avcCodec.url_info[0];
            selectedUrl = urlInfo.host + avcCodec.base_url + urlInfo.extra;
          }
        }
      }

      // 次优备选：如果无 HLS，回退到 FLV (http_stream)
      if (!selectedUrl) {
        const flvStream = streams.find((s) => s.protocol_name === "http_stream");
        if (flvStream && Array.isArray(flvStream.format) && flvStream.format.length > 0) {
          const flvFormat = flvStream.format[0];
          if (flvFormat && Array.isArray(flvFormat.codec) && flvFormat.codec.length > 0) {
            const codec = flvFormat.codec.find((c) => c.codec_name === "avc") || flvFormat.codec[0];
            if (codec && Array.isArray(codec.url_info) && codec.url_info.length > 0) {
              const urlInfo = codec.url_info[0];
              selectedUrl = urlInfo.host + codec.base_url + urlInfo.extra;
            }
          }
        }
      }

      // 终极兜底：第一个可用格式
      if (!selectedUrl && streams[0]?.format?.[0]?.codec?.[0]?.url_info?.[0]) {
        const fallbackCodec = streams[0].format[0].codec[0];
        const urlInfo = fallbackCodec.url_info[0];
        selectedUrl = urlInfo.host + fallbackCodec.base_url + urlInfo.extra;
      }

      if (!selectedUrl) {
        return res.status(404).send(`Room ${inputId} stream format not supported`);
      }

      console.log(`[BiliProxy] Success: 302 redirecting Room ${inputId} (real: ${realRoomId}) to live stream: ${selectedUrl.slice(0, 80)}...`);
      res.setHeader("Location", selectedUrl);
      res.setHeader("Cache-Control", "no-cache, no-store, must-revalidate");
      return res.status(302).end();
    } else {
      return res.status(404).send(`Room ${inputId} stream not found`);
    }
  } catch (err) {
    console.error("[BiliProxy] Error:", err.message);
    return res.status(502).send("API Failed: " + err.message);
  }
};
