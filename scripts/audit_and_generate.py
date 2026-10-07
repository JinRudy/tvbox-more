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
    
    port_part = ""
    host = netloc
    if ":" in netloc:
        parts = netloc.split(":", 1)
        host = parts[0]
        port_part = ":" + parts[1]
        
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

def is_valid_tvbox_content(body: str) -> bool:
    """
    对齐 Android TVBox Google Gson Lenient(宽松容错) 校验规则：
    允许注释、未加前引号的 key、尾随逗号等
    """
    if len(body) < 30:
        return False
    try:
        fixed = re.sub(r'^\s*([a-zA-Z0-9_]+)\"\s*:', r'    "\1":', body, flags=re.M)
        lines = [l for l in fixed.splitlines() if not l.strip().startswith('//')]
        clean = re.sub(r',\s*([\]}])', r'\1', '\n'.join(lines))
        data = json.loads(clean, strict=False)
        return isinstance(data, dict) and ('sites' in data or 'urls' in data)
    except Exception:
        # 若仍有特殊格式，只要包含 sites 且非空即算有效
        return '"sites"' in body and len(body) >= 200

def check_url_liveness(item: dict, timeout=6) -> tuple[dict, bool, str, float]:
    """
    并发测活与内容安全审核：
    返回 (item, is_alive, error_or_info, response_time)
    """
    raw_url = item["url"]
    name = item["name"]

    if is_blacklisted(raw_url, name):
        return (item, False, "🚫 命中恶意黑名单 (Blacklisted)", 0.0)

    url = to_punycode_url(raw_url)
    item["url"] = url
    
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
                body = response.read(524288).decode("utf-8-sig", errors="ignore").strip()
                
                # 1. 深度安全审查：检测恶意弹窗遮罩及流氓引流行为
                warning_match = re.search(r'\"warningText\"\s*:\s*\"([^\"]+)\"', body)
                if warning_match:
                    warning_text = warning_match.group(1)
                    for pat in MALICIOUS_WARNING_PATTERNS:
                        if re.search(pat, warning_text, re.IGNORECASE):
                            return (item, False, f"🚫 恶意弹窗遮罩: [{warning_text[:25]}...]", elapsed)
                
                for pat in [r"微信小程序搜【", r"前往.*获取影视仓", r"starlink\.fan"]:
                    if re.search(pat, body, re.IGNORECASE):
                        return (item, False, f"🚫 包含流氓导流信息", elapsed)

                # 2. 对齐 TVBox Gson 宽松模式验证配置
                if is_valid_tvbox_content(body):
                    return (item, True, f"HTTP {status}", elapsed)
                return (item, False, "内容非有效TVBox配置或空源", elapsed)
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

# 精选候选源定义（经过真机搜片实测加权编排）
# priority 越大越靠前
CANDIDATE_URLS = [
    # === T0 绝代双骄与核心主力 (高优先级置顶) ===
    {"name": "肥猫主仓", "url": "http://肥猫.net/", "category": "core", "priority": 100},
    {"name": "饭太硬主仓", "url": "https://qist.wyfc.qzz.io/fty.json", "category": "core", "priority": 99},
    {"name": "饭太硬0826", "url": "https://qist.wyfc.qzz.io/0826.json", "category": "core", "priority": 98},
    {"name": "饭太硬增强0821", "url": "https://qist.wyfc.qzz.io/0821.json", "category": "core", "priority": 97},
    {"name": "王二小新仓", "url": "https://9280.kstore.vip/newwex.json", "category": "core", "priority": 96},
    {"name": "小盒子综合", "url": "http://xhztv.top/xhz", "category": "core", "priority": 95},
    {"name": "潇洒Qist", "url": "https://qist.wyfc.qzz.io/xiaosa/api.json", "category": "core", "priority": 94},

    # === 体育专线 ===
    {"name": "高天JSM体育", "url": "https://qist.wyfc.qzz.io/jsm.json", "category": "sports", "priority": 85},
    {"name": "小马体育", "url": "https://szyyds.cn/tv/x.json", "category": "sports", "priority": 84},
    {"name": "东篱体育", "url": "https://gh-proxy.com/https://raw.githubusercontent.com/chitue/dongliTV/main/api.json", "category": "sports", "priority": 83},

    # === 少儿动漫 ===
    {"name": "动漫城专线", "url": "https://www.yingm.cc/dm/dm.json", "category": "children", "priority": 80},

    # === 优质综合影视线路 (直连切片源丰富) ===
    {"name": "高天JS线路", "url": "https://qist.wyfc.qzz.io/js.json", "category": "cinema", "priority": 75},
    {"name": "一木自用", "url": "https://gh-proxy.com/https://raw.githubusercontent.com/xianyuyimu/TVBOX-/main/TVBox/%E4%B8%80%E6%9C%A8%E8%87%AA%E7%94%A8.json", "category": "cinema", "priority": 74},
    {"name": "游魂WEX", "url": "https://www.iyouhun.com/tv/wex", "category": "cinema", "priority": 73},
    {"name": "牛二新仓", "url": "https://9280.kstore.space/newwex.json", "category": "cinema", "priority": 72},
    {"name": "王二小WEX", "url": "https://9280.kstore.space/wex.json", "category": "cinema", "priority": 71},
    {"name": "玄珠线路", "url": "https://jihulab.com/xuanzhuapp/xzys/-/raw/main/xzvip.json", "category": "cinema", "priority": 70},
    {"name": "L佬线路", "url": "https://android.lushunming.qzz.io/json/index.json", "category": "cinema", "priority": 69},
    {"name": "SVIP超清源", "url": "https://gh-proxy.com/https://raw.githubusercontent.com/xmbjm/svip/refs/heads/main/svip.json", "category": "cinema", "priority": 68},
    {"name": "高天FM0827", "url": "https://qist.wyfc.qzz.io/0827.json", "category": "cinema", "priority": 67},
    {"name": "高天99188", "url": "https://qist.wyfc.qzz.io/99188.json", "category": "cinema", "priority": 66},
    {"name": "高天9918", "url": "https://qist.wyfc.qzz.io/9918.json", "category": "cinema", "priority": 65},
    {"name": "饭太硬PG0825", "url": "https://qist.wyfc.qzz.io/0825.json", "category": "cinema", "priority": 64},
    {"name": "高天电视", "url": "https://qist.wyfc.qzz.io/dianshi.json", "category": "cinema", "priority": 63},
    {"name": "VIP线路", "url": "https://700sjro44343.vicp.fun/vip/vip/tv.json", "category": "cinema", "priority": 62},
    {"name": "VIP备用0211", "url": "https://700sjro44343.vicp.fun/eggp/0211/tv.json", "category": "cinema", "priority": 61},
    {"name": "TSQ荐片", "url": "https://tv.203511.xyz/0821.json", "category": "cinema", "priority": 60},
    {"name": "鹏九线路", "url": "https://mcp2016.github.io/TVBox/pj.json", "category": "cinema", "priority": 59},
    
    # 俊于线路（降级至后排备用，因目标站老化，基本仅靠360官方通道提供结果）
    {"name": "俊于线路(360备用)", "url": "http://home.jundie.top:81/top98.json", "category": "cinema", "priority": 30},
]

# 高可用直播源定义 (用于根节点 lives，包含网络平台直播与电视直播)
HIGH_QUALITY_LIVES = [
    {
        "name": "🎮多平台网络直播 (虎牙/斗鱼/抖音/B站专线)",
        "type": 0,
        "url": "https://live.yang-1989.eu.org/Live.m3u",
        "playerType": 1
    },
    {
        "name": "📡全国央卫高清精选 (Gather综合源)",
        "type": 0,
        "url": "https://gh-proxy.com/https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u",
        "epg": "https://epg.112114.xyz/?ch={name}&date={date}",
        "logo": "https://epg.112114.xyz/logo/{name}.png",
        "playerType": 1
    },
    {
        "name": "📡全国央卫频道 (CDN高速镜像)",
        "type": 0,
        "url": "https://cdn.jsdelivr.net/gh/YanG-1989/m3u@main/Gather.m3u",
        "epg": "https://epg.112114.xyz/?ch={name}&date={date}",
        "logo": "https://epg.112114.xyz/logo/{name}.png",
        "playerType": 2
    }
]

def main():
    print("=" * 60)
    print("开始对多仓源进行并发健康检测、Gson宽容解析与加权编排...")
    print("=" * 60)

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

    # 按照分类和显式 priority 权重进行严格排序
    cat_order = {"core": 1, "sports": 2, "children": 3, "cinema": 4}
    cat_icons = {
        "core": "⭐[精选主力]",
        "sports": "⚽[体育专线]",
        "children": "👶[少儿动漫]",
        "cinema": "🎬[综合影视]"
    }

    # 排序键：大类顺序 -> 权重降序 -> 响应耗时升序
    alive_results.sort(key=lambda x: (
        cat_order.get(x[0]["category"], 99),
        -x[0].get("priority", 50),
        x[1]
    ))

    formatted_urls = []
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

    final_output = {
        "urls": formatted_urls,
        "lives": HIGH_QUALITY_LIVES
    }

    output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../tvboxmuti.json"))
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=4)

    print(f"\n🎉 重新生成成功！已写入文件: {output_path}")
    print(f"包含纯净有效多仓源: {len(formatted_urls)} 条")
    print(f"包含高质量直播源: {len(HIGH_QUALITY_LIVES)} 组")

if __name__ == "__main__":
    main()
