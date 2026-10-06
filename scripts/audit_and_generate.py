import json
import os
import re
import socket
import ssl
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urlunparse
import urllib.request

def to_punycode_url(url: str) -> str:
    """将 URL 中的中文域名转换为标准的 Punycode"""
    parsed = urlparse(url.strip())
    netloc = parsed.netloc
    
    # 分割端口
    port_part = ""
    host = netloc
    if ":" in netloc:
        parts = netloc.split(":", 1)
        host = parts[0]
        port_part = ":" + parts[1]
        
    # 如果含有中文字符，进行 idna 编码
    if re.search(r'[\u4e00-\u9fa5]', host):
        try:
            host = host.encode("idna").decode("ascii")
        except Exception:
            pass
            
    new_netloc = host + port_part
    return urlunparse((parsed.scheme, new_netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))

def check_url_liveness(item: dict, timeout=5) -> tuple[dict, bool, str, float]:
    """
    并发测活检查：
    返回 (item, is_alive, error_or_info, response_time)
    """
    raw_url = item["url"]
    url = to_punycode_url(raw_url)
    item["url"] = url # 更新为安全URL
    
    start_time = time.time()
    headers = {
        "User-Agent": "okhttp/3.15 TVBox/1.0.0 (Linux; Android 10)",
        "Accept": "*/*"
    }
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
            status = response.status
            elapsed = time.time() - start_time
            if status in (200, 206):
                # 读取前 1024 字节验证是否为有效文本或数据，避免空白页或404拦截页
                sample = response.read(1024).decode("utf-8", errors="ignore").strip()
                if len(sample) > 20:
                    # 检查是否有典型的配置特征
                    is_config = any(kw in sample for kw in ["{", "[", "spider", "sites", "urls", "lives", "store", "vip", "#EXTM3U"])
                    # 有些是 base64 加密的
                    if is_config or len(sample) >= 50:
                        return (item, True, f"HTTP {status}", elapsed)
                return (item, False, f"内容过短或疑似失效({len(sample)}b)", elapsed)
            else:
                return (item, False, f"HTTP {status}", elapsed)
    except Exception as e:
        elapsed = time.time() - start_time
        err_msg = str(e)
        if "timed out" in err_msg.lower():
            err_msg = "超时 (Timeout)"
        elif "certificate" in err_msg.lower():
            err_msg = "SSL证书错误"
        elif "connection refused" in err_msg.lower():
            err_msg = "连接被拒"
        elif "nodename nor servname provided" in err_msg.lower():
            err_msg = "域名无法解析 (DNS Error)"
        return (item, False, err_msg, elapsed)

# 基础候选源定义
CANDIDATE_URLS = [
    # 本地原有核心源
    {"name": "饭太硬主仓", "url": "https://qist.wyfc.qzz.io/fty.json", "category": "core"},
    {"name": "饭太硬备用(直连)", "url": "http://www.饭太硬.net/tv", "category": "core"},
    {"name": "肥猫主仓", "url": "http://肥猫.net/", "category": "core"},
    {"name": "胖鸭线路", "url": "https://tv.xn--yhqu5zs87a.top", "category": "core"},
    {"name": "王二小新仓", "url": "https://9280.kstore.vip/newwex.json", "category": "core"},
    {"name": "俊于线路", "url": "http://home.jundie.top:81/top98.json", "category": "core"},
    {"name": "小盒子综合", "url": "http://xhztv.top/xhz", "category": "core"},
    {"name": "摸鱼线路", "url": "https://6800.kstore.vip/fish.json", "category": "core"},
    {"name": "小苹果线路", "url": "https://bitbucket.org/xduo/duoapi/raw/master/xpg.json", "category": "core"},
    
    # 体育与特殊专线
    {"name": "东篱体育", "url": "https://gh-proxy.com/https://raw.githubusercontent.com/chitue/dongliTV/main/api.json", "category": "sports"},
    {"name": "高天JSM体育", "url": "https://qist.wyfc.qzz.io/jsm.json", "category": "sports"},
    {"name": "小马体育", "url": "https://szyyds.cn/tv/x.json", "category": "sports"},
    {"name": "无敌剪影体育", "url": "http://550.3vcn.work/wdjyys.json", "category": "sports"},

    # 少儿与动漫专线
    {"name": "夜猫少儿", "url": "https://jihulab.com/ymz1231/xymz/-/raw/main/ymshaoer", "category": "children"},
    {"name": "动漫城专线", "url": "https://www.yingm.cc/dm/dm.json", "category": "children"},

    # 综合影视线路
    {"name": "饭太硬0826", "url": "https://qist.wyfc.qzz.io/0826.json", "category": "cinema"},
    {"name": "饭太硬增强0821", "url": "https://qist.wyfc.qzz.io/0821.json", "category": "cinema"},
    {"name": "饭太硬PG0825", "url": "https://qist.wyfc.qzz.io/0825.json", "category": "cinema"},
    {"name": "高天FM0827", "url": "https://qist.wyfc.qzz.io/0827.json", "category": "cinema"},
    {"name": "高天JS线路", "url": "https://qist.wyfc.qzz.io/js.json", "category": "cinema"},
    {"name": "高天367", "url": "https://qist.wyfc.qzz.io/367.json", "category": "cinema"},
    {"name": "高天9918", "url": "https://qist.wyfc.qzz.io/9918.json", "category": "cinema"},
    {"name": "高天99188", "url": "https://qist.wyfc.qzz.io/99188.json", "category": "cinema"},
    {"name": "高天电视", "url": "https://qist.wyfc.qzz.io/dianshi.json", "category": "cinema"},
    {"name": "潇洒Qist", "url": "https://qist.wyfc.qzz.io/xiaosa/api.json", "category": "cinema"},
    {"name": "欧歌主线", "url": "https://xn--sdds-rp5imh.v.nxog.top/apitv.php?id=3", "category": "cinema"},
    {"name": "小盒子4K", "url": "http://xhztv.top/4k.json", "category": "cinema"},
    {"name": "一木自用", "url": "https://gh-proxy.com/https://raw.githubusercontent.com/xianyuyimu/TVBOX-/main/TVBox/%E4%B8%80%E6%9C%A8%E8%87%AA%E7%94%A8.json", "category": "cinema"},
    {"name": "牛二新仓", "url": "https://9280.kstore.space/newwex.json", "category": "cinema"},
    {"name": "王二小WEX", "url": "https://9280.kstore.space/wex.json", "category": "cinema"},
    {"name": "驸马线路", "url": "http://fmys.top/fmys.json", "category": "cinema"},
    {"name": "鹏九线路", "url": "https://mcp2016.github.io/TVBox/pj.json", "category": "cinema"},
    {"name": "月儿线路", "url": "https://jihulab.com/yueer/yueera/-/raw/main/11.17/yueer.json", "category": "cinema"},
    {"name": "玄珠线路", "url": "https://jihulab.com/xuanzhuapp/xzys/-/raw/main/xzvip.json", "category": "cinema"},
    {"name": "dxawi线路", "url": "https://dxawi.github.io/0/0.json", "category": "cinema"},
    {"name": "TSQ荐片", "url": "https://tv.203511.xyz/0821.json", "category": "cinema"},
    {"name": "L佬线路", "url": "https://android.lushunming.qzz.io/json/index.json", "category": "cinema"},
    {"name": "鸭先知IP124", "url": "http://124.223.214.31:8/api.json", "category": "cinema"},
    {"name": "鸭先知IP47", "url": "http://47.96.82.41:5188/api.json", "category": "cinema"},
    {"name": "VIP线路", "url": "https://700sjro44343.vicp.fun/vip/vip/tv.json", "category": "cinema"},
    {"name": "VIP备用0211", "url": "https://700sjro44343.vicp.fun/eggp/0211/tv.json", "category": "cinema"},
    {"name": "微视界", "url": "https://ym.wya6.cn/", "category": "cinema"},
    {"name": "肥猫影视备用", "url": "http://xn--5mqx81b535a.com/", "category": "cinema"},
    {"name": "饭太硬XYZ线路", "url": "https://fty.888484.xyz/tv", "category": "cinema"},
    {"name": "游魂WEX", "url": "https://www.iyouhun.com/tv/wex", "category": "cinema"},
    {"name": "刘老六CDN", "url": "https://cdn.jsdelivr.net/gh/liu673cn/box@main/m.json", "category": "cinema"},
    {"name": "刘老六直连", "url": "https://raw.liucn.cc/box/m.json", "category": "cinema"},
    {"name": "SVIP超清源", "url": "https://gh-proxy.com/https://raw.githubusercontent.com/xmbjm/svip/refs/heads/main/svip.json", "category": "cinema"},
    {"name": "9xi4o线路", "url": "https://9xi4o.tk/0725.json", "category": "cinema"},
    {"name": "小盒子多仓", "url": "http://xhztv.top/dc", "category": "multi"},
    {"name": "挺好多仓", "url": "http://ztha.top/TVBox/GYCK.json", "category": "multi"},
    {"name": "鹏九多仓", "url": "https://mcp2016.github.io/TVBox/urls.json", "category": "multi"},
]

# 高可用电视直播源定义 (用于根节点 lives)
HIGH_QUALITY_LIVES = [
    {
        "name": "📡全国央视卫视超清 (IPv6优先/含4K)",
        "type": 0,
        "url": "https://live.fanmingming.com/tv/m3u/ipv6.m3u",
        "epg": "https://epg.112114.xyz/?ch={name}&date={date}",
        "logo": "https://epg.112114.xyz/logo/{name}.png",
        "playerType": 1
    },
    {
        "name": "📡全国央视卫视高清 (IPv4通用推荐)",
        "type": 0,
        "url": "https://live.fanmingming.com/tv/m3u/ipv4.m3u",
        "epg": "https://epg.112114.xyz/?ch={name}&date={date}",
        "logo": "https://epg.112114.xyz/logo/{name}.png",
        "playerType": 1
    },
    {
        "name": "📡综合电视频道汇总 (Gather源)",
        "type": 0,
        "url": "https://gh-proxy.com/https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u",
        "epg": "https://epg.112114.xyz/?ch={name}&date={date}",
        "playerType": 2
    },
    {
        "name": "📡备用精选电视频道 (TXT格式)",
        "type": 0,
        "url": "https://gh-proxy.com/https://raw.githubusercontent.com/Ftindy/IPTV-URL/main/live.txt",
        "playerType": 1
    }
]

def main():
    print("=" * 60)
    print("开始对所有多仓与链路候选源进行并发健康检测...")
    print("=" * 60)

    # 去重处理
    unique_candidates = []
    seen_urls = set()
    for item in CANDIDATE_URLS:
        normalized_url = to_punycode_url(item["url"])
        if normalized_url not in seen_urls:
            seen_urls.add(normalized_url)
            unique_candidates.append(item)

    print(f"待检测去重源总数: {len(unique_candidates)}")

    alive_results = []
    dead_results = []

    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = {executor.submit(check_url_liveness, item): item for item in unique_candidates}
        for future in as_completed(futures):
            item, is_alive, info, elapsed = future.result()
            if is_alive:
                alive_results.append((item, elapsed, info))
                print(f"[✅ 有效] {item['name']} ({elapsed:.2f}s) - {info}")
            else:
                dead_results.append((item, elapsed, info))
                print(f"[❌ 失效] {item['name']} ({elapsed:.2f}s) - {info}")

    print("\n" + "=" * 60)
    print(f"测活检测完成: 有效源 {len(alive_results)} 个, 失效源 {len(dead_results)} 个")
    print("=" * 60)

    # 分类与排序规范
    # 类别权重
    cat_order = {"core": 1, "sports": 2, "children": 3, "cinema": 4, "multi": 5}
    cat_icons = {
        "core": "⭐[精选主力]",
        "sports": "⚽[体育专线]",
        "children": "👶[少儿动漫]",
        "cinema": "🎬[综合影视]",
        "multi": "📦[综合多仓]"
    }

    # 按分类及响应时间排序
    alive_results.sort(key=lambda x: (cat_order.get(x[0]["category"], 99), x[1]))

    formatted_urls = []
    # 1. 首先加入纯电视直播单仓入口（满足老旧盒子切仓看直播需求）
    formatted_urls.append({
        "url": "https://gh-proxy.com/https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u",
        "name": "📡[电视直播] - 全国央卫超清专线"
    })

    # 2. 依次编排有效源
    index_map = {}
    for item, elapsed, info in alive_results:
        cat = item["category"]
        prefix = cat_icons.get(cat, "📺[其他]")
        index_map[cat] = index_map.get(cat, 0) + 1
        num = index_map[cat]
        display_name = f"{prefix} {num}-{item['name']}"
        formatted_urls.append({
            "url": item["url"],
            "name": display_name
        })

    # 3. 如果有效源中某些战略性主仓（如肥猫、饭太硬直连）因海外/国内网络偶发超时，将其作为备用线路放置在容灾专区
    # 保证饭太硬与肥猫至少有一个可用入口
    has_fty = any("饭太硬" in u["name"] for u in formatted_urls)
    has_fm = any("肥猫" in u["name"] for u in formatted_urls)

    if not has_fty:
        formatted_urls.append({
            "url": "http://www.xn--sss604efuw.net/tv",
            "name": "⭐[精选主力] 备用-饭太硬官方直连"
        })
    if not has_fm:
        formatted_urls.append({
            "url": "http://xn--5mqx81b535a.com/",
            "name": "⭐[精选主力] 备用-肥猫官方备用"
        })

    # 组装最终 JSON
    final_output = {
        "urls": formatted_urls,
        "lives": HIGH_QUALITY_LIVES
    }

    output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../tvboxmuti.json"))
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=4)

    print(f"\n🎉 重新生成成功！已写入文件: {output_path}")
    print(f"包含有效多仓源: {len(formatted_urls)} 条")
    print(f"包含高质量直播源: {len(HIGH_QUALITY_LIVES)} 组")

if __name__ == "__main__":
    main()
