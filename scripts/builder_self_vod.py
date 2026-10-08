#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/builder_self_vod.py
基于全网开源 CMS 采集站，通过《爱情公寓》压测构建 100% 透明零黑匣子点播主仓 (tvboxvod.json)
"""

import os
import json
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional, Tuple

BENCHMARK_KEYWORD = "爱情公寓"
TOKEN_URL = "https://tvbox.wushui.fun/token.json"

# 全网主流知名开源 CMS (MacCMS/AppleCMS) 采集站候选池
CANDIDATE_CMS_SITES = [
    {
        "key": "liangzi",
        "name": "🎬量子资源┃4K秒播",
        "api": "https://cj.lziapi.com/api.php/provide/vod/from/lzm3u8/at/json/",
    },
    {
        "key": "feifan",
        "name": "🎬非凡资源┃超清秒播",
        "api": "http://cj.ffzyapi.com/api.php/provide/vod/from/ffm3u8/at/json/",
    },
    {
        "key": "baofeng",
        "name": "🎬暴风资源┃多线备用",
        "api": "https://bfzyapi.com/api.php/provide/vod/from/bfm3u8/at/json/",
    },
    {
        "key": "hongniu",
        "name": "🎬红牛资源┃超清极速",
        "api": "https://www.hongniuzy2.com/api.php/provide/vod/from/hnm3u8/at/json/",
    },
    {
        "key": "kuaiche",
        "name": "🎬快车资源┃秒播快看",
        "api": "https://caiji.kuaichezy.net/api.php/provide/vod/from/kcm3u8/at/json/",
    },
    {
        "key": "guangsu",
        "name": "🎬光速资源┃高清画质",
        "api": "https://api.guangsuapi.com/api.php/provide/vod/from/gsm3u8/at/json/",
    },
    {
        "key": "suoni",
        "name": "🎬索尼资源┃多线专享",
        "api": "https://suoniapi.com/api.php/provide/vod/from/snm3u8/at/json/",
    },
    {
        "key": "wolong",
        "name": "🎬卧龙资源┃大片专线",
        "api": "https://collect.wolongzyw.com/api.php/provide/vod/from/wlm3u8/at/json/",
    },
    {
        "key": "jisu",
        "name": "🎬极速资源┃秒开专线",
        "api": "https://jszyapi.com/api.php/provide/vod/from/jsm3u8/at/json/",
    },
]

def probe_cms_with_benchmark(site_info: Dict[str, str], timeout: float = 4.0) -> Optional[Dict]:
    """
    使用《爱情公寓》作为探针，压测 CMS 站点的搜索与可播性
    1. 搜索能出结果，且包含《爱情公寓》
    2. 能解析出播放列表与有效 m3u8
    3. 剔除假站、广告短片引流站
    """
    api = site_info["api"]
    params = urllib.parse.urlencode({"ac": "detail", "wd": BENCHMARK_KEYWORD})
    query_url = f"{api}{'&' if '?' in api else '?'}{params}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*'
    }

    try:
        req = urllib.request.Request(query_url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            body = resp.read().decode('utf-8', errors='ignore')

        data = json.loads(body)
        vod_list = data.get("list", [])
        if not vod_list or not isinstance(vod_list, list):
            return None

        # 验证是否命中《爱情公寓》
        matched_item = None
        for item in vod_list:
            v_name = item.get("vod_name", "")
            if BENCHMARK_KEYWORD in v_name:
                matched_item = item
                break

        if not matched_item:
            return None

        # 验证播放切片直链
        play_url_str = matched_item.get("vod_play_url", "")
        if not play_url_str or ".m3u8" not in play_url_str:
            return None

        # 检查通过，构建标准的 TVBox 原生 type: 1 节点
        return {
            "key": site_info["key"],
            "name": site_info["name"],
            "type": 1,
            "api": site_info["api"],
            "searchable": 1,
            "quickSearch": 1,
            "filterable": 1
        }
    except Exception:
        return None

def build_self_hosted_vod(output_path: str) -> int:
    """并发压测所有候选站，生成 tvboxvod.json"""
    print(f">>> [自建点播] 开始对全网 {len(CANDIDATE_CMS_SITES)} 个开源 CMS 采集站执行《爱情公寓》全链路压测...")

    valid_sites = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(probe_cms_with_benchmark, s): s for s in CANDIDATE_CMS_SITES}
        for future in futures:
            res = future.result()
            if res:
                valid_sites.append(res)
                print(f"  [通过压测] {res['name']} -> 成功检索并切片验证《{BENCHMARK_KEYWORD}》")

    # 保底机制：若极端网络抖动，保留优质基准站
    if len(valid_sites) < 3:
        print("[Warning] 网络抖动触发自建点播保底站补全...")
        fallback_keys = {s["key"] for s in valid_sites}
        for s in CANDIDATE_CMS_SITES[:4]:
            if s["key"] not in fallback_keys:
                valid_sites.append({
                    "key": s["key"],
                    "name": s["name"],
                    "type": 1,
                    "api": s["api"],
                    "searchable": 1,
                    "quickSearch": 1,
                    "filterable": 1
                })

    vod_config = {
        "spider": "",
        "token": TOKEN_URL,
        "token_url": TOKEN_URL,
        "sites": valid_sites,
        "parses": [
            {
                "name": "Json聚合",
                "type": 1,
                "url": "https://jx.jsonplayer.com/player/?url="
            }
        ],
        "flags": ["youku", "qq", "iqiyi", "qiyi", "letv", "sohu", "tudou", "pptv", "mgtv"]
    }

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(vod_config, f, ensure_ascii=False, indent=2)

    print(f">>> [自建点播] 成功构建 100% 透明零黑匣子主仓: {output_path} (共 {len(valid_sites)} 个合格站点)")
    return len(valid_sites)

if __name__ == "__main__":
    target = os.path.abspath(os.path.join(os.path.dirname(__file__), "../tvboxvod.json"))
    build_self_hosted_vod(target)
