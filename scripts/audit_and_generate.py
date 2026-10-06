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

# 永久拉黑的恶意/流氓域名或IP指示词
BLACKLIST_INDICATORS = [
    "124.223.214.31",
    "47.96.82.41",
    "starlink.fan",
    "yueera",
]

# 恶意弹窗/遮罩引流过滤正则
MALICIOUS_WARNING_PATTERNS = [
    r"到期关闭",
    r"更换.*地址",
    r"微信小程序",
    r"关注公众号",
    r"QQ[：:\s]*\d+",
    r"防失联",
    r"群号",
    r"进群",
    r"购买",
    r"付费",
    r"starlink",
    r"淘软件",
    r"软件小哥哥",
    r"扫码"
]

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

def is_blacklisted(url: str, name: str = "") -> bool:
    """检查是否属于黑名单"""
    for bl in BLACKLIST_INDICATORS:
        if bl in url or bl in name:
            return True
    return False

def check_url_liveness(item: dict, timeout=5) -> tuple[dict, bool, str, float]:
    """
    并发测活与内容安全审核：
    返回 (item, is_alive, error_or_info, response_time)
    """
    raw_url = item["url"]
    name = item["name"]

    # 1. 前置黑名单拦截
    if is_blacklisted(raw_url, name):
        return (item, False, "🚫 命中恶意黑名单 (Blacklisted)", 0.0)

    url = to_punycode_url(raw_url)
    item["url"] = url  # 更新为安全URL
    
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
                # 读取全部内容（至多 256KB 用于快速扫描）进行安全与有效性审查
                body = response.read(262144).decode("utf-8", errors="ignore").strip()
                if len(body) < 20:
                    return (item, False, f"内容过短或疑似失效({len(body)}b)", elapsed)

                # 2. 深度安全审查：检测恶意弹窗遮罩及流氓引流行为
                # 检查 warningText 字段
                warning_match = re.search(r'\"warningText\"\s*:\s*\"([^\"]+)\"', body)
                if warning_match:
                    warning_text = warning_match.group(1)
                    for pat in MALICIOUS_WARNING_PATTERNS:
                        if re.search(pat, warning_text, re.IGNORECASE):
                            return (item, False, f"🚫 恶意弹窗遮罩: [{warning_text[:30]}...]", elapsed)
                
                # 检查全局引流恶意词（如站点名称中强行植入小程序导流）
                for pat in [r"微信小程序搜【", r"前往.*获取影视仓", r"starlink\.fan"]:
                    if re.search(pat, body, re.IGNORECASE):
                        return (item, False, f"🚫 包含流氓导流信息 (命中 {pat})", elapsed)

                # 3. 基础有效性检查
                is_config = any(kw in body for kw in ["{", "[", "spider", "sites", "urls", "lives", "store", "vip", "#EXTM3U"])
                if is_config or len(body) >= 50:
                    return (item, True, f"HTTP {status}", elapsed)
                return (item, False, "非有效 TVBox 配置内容", elapsed)
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

# 纯净候选源定义（已剔除 124、47、月儿等流氓弹窗源）
CANDIDATE_URLS = [
    # 核心优质主力仓
    {"name": "饭太硬主仓", "url": "https://qist.wyfc.qzz.io/fty.json", "category": "core"},
    {"name": "肥猫主仓", "url": "http://肥猫.net/", "category": "core"},
    {"name": "胖鸭线路", "url": "https://tv.xn--yhqu5zs87a.top", "category": "core"},
    {"name": "王二小新仓", "url": "https://9280.kstore.vip/newwex.json", "category": "core"},
    {"name": "俊于线路", "url": "http://home.jundie.top:81/top98.json", "category": "core"},
    {"name": "小盒子综合", "url": "http://xhztv.top/xhz", "category": "core"},
    
    # 体育专线
    {"name": "东篱体育", "url": "https://gh-proxy.com/https://raw.githubusercontent.com/chitue/dongliTV/main/api.json", "category": "sports"},
    {"name": "高天JSM体育", "url": "https://qist.wyfc.qzz.io/jsm.json", "category": "sports"},
    {"name": "小马体育", "url": "https://szyyds.cn/tv/x.json", "category": "sports"},
    {"name": "无敌剪影体育", "url": "http://550.3vcn.work/wdjyys.json", "category": "sports"},

    # 少儿与动漫专线
    {"name": "夜猫少儿", "url": "https://jihulab.com/ymz1231/xymz/-/raw/main/ymshaoer", "category": "children"},
    {"name": "动漫城专线", "url": "https://www.yingm.cc/dm/dm.json", "category": "children"},

    # 纯净综合影视线路
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
    {"name": "小盒子4K", "url": "http://xhztv.top/4k.json", "category": "cinema"},
    {"name": "一木自用", "url": "https://gh-proxy.com/https://raw.githubusercontent.com/xianyuyimu/TVBOX-/main/TVBox/%E4%B8%80%E6%9C%A8%E8%87%AA%E7%94%A8.json", "category": "cinema"},
    {"name": "牛二新仓", "url": "https://9280.kstore.space/newwex.json", "category": "cinema"},
    {"name": "王二小WEX", "url": "https://9280.kstore.space/wex.json", "category": "cinema"},
    {"name": "鹏九线路", "url": "https://mcp2016.github.io/TVBox/pj.json", "category": "cinema"},
    {"name": "玄珠线路", "url": "https://jihulab.com/xuanzhuapp/xzys/-/raw/main/xzvip.json", "category": "cinema"},
    {"name": "dxawi线路", "url": "https://dxawi.github.io/0/0.json", "category": "cinema"},
    {"name": "TSQ荐片", "url": "https://tv.203511.xyz/0821.json", "category": "cinema"},
    {"name": "L佬线路", "url": "https://android.lushunming.qzz.io/json/index.json", "category": "cinema"},
    {"name": "VIP线路", "url": "https://700sjro44343.vicp.fun/vip/vip/tv.json", "category": "cinema"},
    {"name": "VIP备用0211", "url": "https://700sjro44343.vicp.fun/eggp/0211/tv.json", "category": "cinema"},
    {"name": "微视界", "url": "https://ym.wya6.cn/", "category": "cinema"},
    {"name": "饭太硬XYZ线路", "url": "https://fty.888484.xyz/tv", "category": "cinema"},
    {"name": "游魂WEX", "url": "https://www.iyouhun.com/tv/wex", "category": "cinema"},
    {"name": "刘老六CDN", "url": "https://cdn.jsdelivr.net/gh/liu673cn/box@main/m.json", "category": "cinema"},
    {"name": "刘老六直连", "url": "https://raw.liucn.cc/box/m.json", "category": "cinema"},
    {"name": "SVIP超清源", "url": "https://gh-proxy.com/https://raw.githubusercontent.com/xmbjm/svip/refs/heads/main/svip.json", "category": "cinema"},
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
    print("开始对多仓源进行并发健康检测与恶意弹窗/遮罩内容过滤...")
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
                print(f"[✅ 有效纯净] {item['name']} ({elapsed:.2f}s) - {info}")
            else:
                dead_results.append((item, elapsed, info))
                print(f"[❌ 剔除] {item['name']} ({elapsed:.2f}s) - {info}")

    print("\n" + "=" * 60)
    print(f"审查与测活完成: 保留纯净有效源 {len(alive_results)} 个, 拦截剔除源 {len(dead_results)} 个")
    print("=" * 60)

    # 分类与排序规范
    cat_order = {"core": 1, "sports": 2, "children": 3, "cinema": 4, "multi": 5}
    cat_icons = {
        "core": "⭐[精选主力]",
        "sports": "⚽[体育专线]",
        "children": "👶[少儿动漫]",
        "cinema": "🎬[综合影视]",
        "multi": "📦[综合多仓]"
    }

    alive_results.sort(key=lambda x: (cat_order.get(x[0]["category"], 99), x[1]))

    formatted_urls = []
    # 纯电视直播单仓入口
    formatted_urls.append({
        "url": "https://gh-proxy.com/https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u",
        "name": "📡[电视直播] - 全国央卫超清专线"
    })

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

    # 组装最终纯净版 JSON
    final_output = {
        "urls": formatted_urls,
        "lives": HIGH_QUALITY_LIVES
    }

    output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../tvboxmuti.json"))
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=4)

    print(f"\n🎉 纯净版生成成功！已写入文件: {output_path}")
    print(f"包含纯净有效多仓源: {len(formatted_urls)} 条")
    print(f"包含高质量直播源: {len(HIGH_QUALITY_LIVES)} 组")

if __name__ == "__main__":
    main()
