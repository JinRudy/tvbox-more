#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本名称: generate_tvboxlive.py
功能描述: 
    全自动抓取、清洗与聚合全网高质量直播源，生成电视机标准 TXT 格式 (使用 #genre# 分组) 的 tvboxlive.txt。
    支持央视、卫视、体育、少儿动漫、虎牙/斗鱼精品轮播、港澳台专线以及针对海外受限频道的 Cloudflare 免翻代理。
"""

import os
import re
import sys
import urllib.parse
import urllib.request
from typing import Dict, List, Tuple

# 代理前缀，由 Cloudflare Worker 提供中继加速与 M3U8 切片重写
PROXY_PREFIX = "https://tvbox.wushui.fun/proxy?url="

# 黑名单与垃圾关键字过滤
JUNK_KEYWORDS = [
    "更新时间", "維護時間", "维护时间", "測試", "测试", "說明", "说明", 
    "提示", "免費訂閲", "免费订阅", "防失联", "扫码", "关注", "微信", "QQ群", "公众号"
]

JUNK_URL_INDICATORS = [
    "time.mp4", "tg.jpg", "testvideo", "302.mp4", "yang-1989.xyz/v"
]

def fetch_url(url: str, timeout: int = 10) -> str:
    """带重试和 User-Agent 的通用网络抓取"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[Warning] 请求失败: {url} - {e}")
        return ""

def is_clean_channel(name: str, url: str) -> bool:
    """校验频道是否合法、无垃圾广告"""
    name_clean = name.strip()
    url_clean = url.strip()
    
    if not name_clean or not url_clean:
        return False
        
    for kw in JUNK_KEYWORDS:
        if kw in name_clean:
            return False
            
    for ind in JUNK_URL_INDICATORS:
        if ind in url_clean:
            return False
            
    return True

def parse_m3u(content: str, max_items: int = 50) -> List[Tuple[str, str]]:
    """解析 M3U 内容为 (频道名, 播放URL) 列表，并清洗假台"""
    results = []
    lines = content.splitlines()
    curr_name = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            # 提取逗号后的频道名
            parts = line.split(",")
            if len(parts) > 1:
                curr_name = parts[-1].strip()
            else:
                curr_name = "未知频道"
        elif not line.startswith("#"):
            if curr_name and line.startswith("http"):
                if is_clean_channel(curr_name, line):
                    results.append((curr_name, line))
                    if len(results) >= max_items:
                        break
            curr_name = None
            
    return results

def parse_txt_genres(content: str) -> Dict[str, List[Tuple[str, str]]]:
    """解析标准 #genre# 格式的 TXT 源"""
    sections = {}
    curr_genre = None
    
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        if "#genre#" in line:
            genre_name = line.split(",")[0].strip()
            # 忽略包含垃圾关键词的分组
            if any(kw in genre_name for kw in JUNK_KEYWORDS):
                curr_genre = None
                continue
            curr_genre = genre_name
            if curr_genre not in sections:
                sections[curr_genre] = []
        elif curr_genre and "," in line:
            parts = line.split(",", 1)
            c_name = parts[0].strip()
            c_url = parts[1].strip()
            if is_clean_channel(c_name, c_url):
                sections[curr_genre].append((c_name, c_url))
                
    return sections

def get_international_channels() -> List[Tuple[str, str]]:
    """构造精选国际知名大台 (支持直连与 Cloudflare 免翻代理)"""
    raw_channels = [
        # CGTN 官方系列 (免翻直连)
        ("CGTN 英语新闻", "https://amg00405-rakutentv-cgtn-rakuten-i9tar.amagi.tv/master.m3u8"),
        ("CGTN 纪录频道", "https://amg00405-rakutentv-cgtn-rakuten-i9tar.amagi.tv/master.m3u8"),
        
        # 德国之声 DW (直连 + 代理)
        ("DW 德国之声 (直连)", "https://amg01644-amg01644c1-amgplt0343.playout.now3.amagi.tv/ts-eu-w1-n2/playlist/amg01644-amg01644c1-amgplt0343/playlist.m3u8"),
        ("DW 德国之声 (代理)", PROXY_PREFIX + urllib.parse.quote("https://amg01644-amg01644c1-amgplt0343.playout.now3.amagi.tv/ts-eu-w1-n2/playlist/amg01644-amg01644c1-amgplt0343/playlist.m3u8")),
        
        # 日本 NHK World (直连 + 代理)
        ("NHK World-Japan (直连)", "https://masterpl.hls.nhkworld.jp/hls/w/live/smarttv.m3u8"),
        ("NHK World-Japan (代理)", PROXY_PREFIX + urllib.parse.quote("https://masterpl.hls.nhkworld.jp/hls/w/live/smarttv.m3u8")),
        
        # 法国 24 台 France 24 (直连 + 代理)
        ("France 24 法国24 (直连)", "https://live.france24.com/hls/live/2037218-b/F24_EN_HI_HLS/master_5000.m3u8"),
        ("France 24 法国24 (代理)", PROXY_PREFIX + urllib.parse.quote("https://live.france24.com/hls/live/2037218-b/F24_EN_HI_HLS/master_5000.m3u8")),
        
        # 彭博社商业 Bloomberg TV (直连 + 代理)
        ("Bloomberg 彭博财经 (直连)", "https://bloomberg.com/media-manifest/streams/qt.m3u8"),
        ("Bloomberg 彭博财经 (代理)", PROXY_PREFIX + urllib.parse.quote("https://bloomberg.com/media-manifest/streams/qt.m3u8")),
        
        # 半岛电视台 Al Jazeera (直连 + 代理)
        ("Al Jazeera 半岛英语 (直连)", "https://live-hls-apps-aje-fa.getaj.net/AJE/index.m3u8"),
        ("Al Jazeera 半岛英语 (代理)", PROXY_PREFIX + urllib.parse.quote("https://live-hls-apps-aje-fa.getaj.net/AJE/index.m3u8")),
        
        # 英国 BBC 新闻台 (受限台，全量代理)
        ("BBC News (代理)", PROXY_PREFIX + urllib.parse.quote("http://193.46.58.239:8080/BBCTwoHD/index.m3u8")),
        ("BBC America (代理)", PROXY_PREFIX + urllib.parse.quote("http://23.239.31.26:8989/bbcamerica/index.m3u8")),
        
        # 美国 CNN / CBS / ABC 新闻 (受限台，代理)
        ("CNN Prima (代理)", PROXY_PREFIX + urllib.parse.quote("http://88.212.15.19/live/test_cnn_pirma_news/playlist.m3u8")),
        ("ABC News Live (代理)", PROXY_PREFIX + urllib.parse.quote("https://abcnews-streams.akamaized.net/hls/live/2023560/abcnewshudson1/master.m3u8")),
        ("CBS News 24/7 (代理)", PROXY_PREFIX + urllib.parse.quote("https://jmp2.uk/plu-6350fdd266e9ea0007bedec5.m3u8")),
    ]
    return raw_channels

def get_hktw_channels() -> List[Tuple[str, str]]:
    """构造港澳台知名频道 (凤凰系列、TVB翡翠台、TVBS等)"""
    return [
        ("凤凰卫视中文台", "http://223.110.245.139/ott.js.chinamobile.com/PLTV/3/224/3221226922/index.m3u8"),
        ("凤凰卫视中文台(备用)", "https://7612-5516-affc-d88b.kylintv.tv/live/pxinhd_iphone.m3u8"),
        ("凤凰卫视资讯台", "http://223.110.245.167/ott.js.chinamobile.com/PLTV/3/224/3221226923/index.m3u8"),
        ("凤凰卫视资讯台(备用)", "https://cdn6.163189.xyz/163189/fhzx"),
        ("凤凰卫视香港台", "http://r.jdshipin.com/yDoTN"),
        ("TVB 翡翠台", "http://103.172.187.30:12000/stream/mytv/null-1/master.m3u8"),
        ("TVB 翡翠台(备用1)", "http://r.jdshipin.com/qClQf"),
        ("TVB 翡翠台(备用2)", "http://r.jdshipin.com/qrfbg"),
        ("TVB 明珠台", "https://hls-gateway.vpstv.net/streams/476936.m3u8"),
        ("美亚电影台", "http://103.172.187.30:12000/stream/mytv/null-9/master.m3u8"),
        ("天映经典电影", "http://103.58.160.157:8278/720-CELESTIALMOVIES/playlist.m3u8"),
        ("中天娱乐台", "http://23.237.10.66:16372"),
        ("TVBS 亚洲台", "http://38.64.72.148/hls/modn/list/4005/playlist.m3u8"),
        ("台视综合", "http://162.19.247.76:22222/live/taishi/index.m3u8"),
        ("香港国际财经台", PROXY_PREFIX + urllib.parse.quote("https://hoytv-live-stream.hoy.tv/ch76/index-fhd.m3u8")),
    ]

def get_classic_drama_channels() -> List[Tuple[str, str]]:
    """构造经典 24H 连续剧/电影专区 (亮剑、西游记、三国、周星驰、林正英等)"""
    return [
        ("周星驰电影 24H", "https://live.ottiptv.cc/huya/11342412"),
        ("林正英经典 24H", "https://live.ottiptv.cc/huya/30611864"),
        ("亮剑全天轮播 24H", "https://live.ottiptv.cc/douyu/4549169"),
        ("武林外传全天轮播", "https://live.ottiptv.cc/douyu/6906628"),
        ("甄嬛传全天轮播", "https://live.ottiptv.cc/douyu/12560807"),
        ("经典港片影院 24H", "https://live.ottiptv.cc/huya/30509122"),
        ("齐鲁影视展播", "https://live.ottiptv.cc/huya/29807061"),
        ("阿斗电影解说 24H", "https://live.ottiptv.cc/huya/11352958"),
        ("猫和老鼠 24H", "https://live.ottiptv.cc/douyu/12851401"),
        ("名侦探柯南 24H", "https://live.ottiptv.cc/douyu/12890335"),
        ("蜡笔小新 24H", "https://live.ottiptv.cc/douyu/8009547"),
    ]

def main():
    print(">>> [1/5] 抓取 Guovin 高可用国内央视、卫视、数字付费频道...")
    guovin_urls = [
        "https://raw.githubusercontent.com/Guovin/TV/gd/output/result.txt",
        "https://gh-proxy.com/https://raw.githubusercontent.com/Guovin/TV/gd/output/result.txt"
    ]
    guovin_content = ""
    for u in guovin_urls:
        guovin_content = fetch_url(u, timeout=8)
        if guovin_content:
            print(f"成功获取 Guovin 源 ({len(guovin_content)} 字节)")
            break
            
    guovin_sections = parse_txt_genres(guovin_content) if guovin_content else {}

    print(">>> [2/5] 抓取虎牙和斗鱼精品轮播频道...")
    huya_raw = fetch_url("https://sub.ottiptv.cc/huyayqk.m3u", timeout=8)
    douyu_raw = fetch_url("https://sub.ottiptv.cc/douyuyqk.m3u", timeout=8)
    
    huya_channels = parse_m3u(huya_raw, max_items=45) if huya_raw else []
    douyu_channels = parse_m3u(douyu_raw, max_items=45) if douyu_raw else []
    print(f"已获取清洗后的虎牙频道: {len(huya_channels)} 个, 斗鱼频道: {len(douyu_channels)} 个")

    print(">>> [3/5] 构造港澳台、国际频道与经典轮播专区...")
    hktw_channels = get_hktw_channels()
    intl_channels = get_international_channels()
    drama_channels = get_classic_drama_channels()

    print(">>> [4/5] 按照标准 #genre# 分组聚合各频道...")
    output_lines = []

    # 1. 央视频道
    cctv_list = guovin_sections.get("📺央视频道", [])
    if cctv_list:
        output_lines.append("央视频道,#genre#")
        for name, url in cctv_list:
            output_lines.append(f"{name},{url}")
        output_lines.append("")

    # 2. 卫视频道
    ws_list = guovin_sections.get("📡卫视频道", [])
    if ws_list:
        output_lines.append("卫视频道,#genre#")
        for name, url in ws_list:
            output_lines.append(f"{name},{url}")
        output_lines.append("")

    # 3. 央视付费与数字频道
    cctv_pay = guovin_sections.get("💰央视付费频道", [])
    if cctv_pay:
        output_lines.append("央视付费,#genre#")
        for name, url in cctv_pay:
            output_lines.append(f"{name},{url}")
        output_lines.append("")

    # 4. 体育竞技
    sports_list = guovin_sections.get("🏀体育频道", [])
    if sports_list:
        output_lines.append("体育竞技,#genre#")
        for name, url in sports_list:
            output_lines.append(f"{name},{url}")
        output_lines.append("")

    # 5. 港澳台专线
    output_lines.append("港澳台专线,#genre#")
    for name, url in hktw_channels:
        output_lines.append(f"{name},{url}")
    # 合并 Guovin 的港澳台如果存在
    if "🌊港·澳·台" in guovin_sections:
        for name, url in guovin_sections["🌊港·澳·台"]:
            # 简单去重
            if not any(name == item[0] for item in hktw_channels):
                output_lines.append(f"{name},{url}")
    output_lines.append("")

    # 6. 国际频道 (免翻直连 + Cloudflare代理)
    output_lines.append("国际频道(免翻/代理),#genre#")
    for name, url in intl_channels:
        output_lines.append(f"{name},{url}")
    output_lines.append("")

    # 7. 经典剧场 24H 轮播
    output_lines.append("经典剧场24H,#genre#")
    for name, url in drama_channels:
        output_lines.append(f"{name},{url}")
    if "🏛经典剧场" in guovin_sections:
        for name, url in guovin_sections["🏛经典剧场"]:
            output_lines.append(f"{name},{url}")
    output_lines.append("")

    # 8. 虎牙精选
    if huya_channels:
        output_lines.append("虎牙精选,#genre#")
        for name, url in huya_channels:
            output_lines.append(f"{name},{url}")
        output_lines.append("")

    # 9. 斗鱼精选
    if douyu_channels:
        output_lines.append("斗鱼精选,#genre#")
        for name, url in douyu_channels:
            output_lines.append(f"{name},{url}")
        output_lines.append("")

    # 10. 少儿动漫
    anime_list = guovin_sections.get("🪁动画频道", [])
    if anime_list:
        output_lines.append("少儿动漫,#genre#")
        for name, url in anime_list:
            output_lines.append(f"{name},{url}")
        output_lines.append("")

    # 11. 电影频道
    movie_list = guovin_sections.get("🎬电影频道", [])
    if movie_list:
        output_lines.append("电影影院,#genre#")
        for name, url in movie_list:
            output_lines.append(f"{name},{url}")
        output_lines.append("")

    final_content = "\n".join(output_lines)
    
    # 输出写入目标路径
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    target_path = os.path.join(root_dir, "tvboxlive.txt")
    
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(final_content)

    print(f">>> [5/5] 成功生成 tvboxlive.txt！总行数: {len(output_lines)}, 文件大小: {len(final_content.encode('utf-8'))} 字节")
    print(f"写入路径: {target_path}")

if __name__ == "__main__":
    main()
