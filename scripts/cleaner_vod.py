#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/cleaner_vod.py
点播多仓健康体检、死仓与黑匣子剔除，并置顶集成自建透明主仓 (tvboxmuti.json)
"""

import os
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

SELF_HOSTED_TOP_ENTRY = {
    "url": "https://tvbox.wushui.fun/tvboxvod.json",
    "name": "👑[自建纯净] 0-无水全网透明主仓"
}

BLOCKED_NAME_KEYWORDS = ("免费订阅", "加群", "微信", "QQ群", "防失联")

def probe_vod_repository(entry: Dict[str, str], timeout: float = 3.5) -> Optional[Dict[str, str]]:
    """探测单个多仓节点的连通性与合法性"""
    url = entry.get("url", "").strip()
    name = entry.get("name", "").strip()

    if not url or not url.startswith("http"):
        return None

    if any(k in name for k in BLOCKED_NAME_KEYWORDS):
        return None

    # 如果是自建站本身，无需网络探测直接通过
    if "tvboxvod.json" in url or "tvbox.wushui.fun" in url:
        return entry

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': '*/*'
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            body_start = resp.read(2048).decode('utf-8', errors='ignore')

        # 检查是否为合法的 TVBox 规范或至少是文本/JSON
        if any(keyword in body_start for keyword in ["sites", "spider", "urls", "wallpaper", "lives", "{"]):
            return entry
    except Exception:
        # 网络超时或 404/502，剔除该坏仓
        pass

    return None

def clean_and_integrate_muti_vod(muti_path: str) -> int:
    """体检多仓，保留原有分类顺序，剔除死仓并置顶自建主仓"""
    print(f">>> [多仓体检] 开始读取多仓配置: {muti_path}...")
    if not os.path.exists(muti_path):
        print(f"[Error] 未找到多仓文件: {muti_path}")
        return 0

    with open(muti_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_urls = data.get("urls", [])
    print(f">>> [多仓体检] 发现 {len(raw_urls)} 个候选仓位，开始并发健康探测...")

    # 过滤掉原本旧的自建项（若存在），避免重复
    filtered_raw = [
        u for u in raw_urls
        if "tvboxvod.json" not in u.get("url", "") and "自建" not in u.get("name", "")
    ]

    valid_entries = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        # 保持原本的先后顺序映射
        results = list(executor.map(probe_vod_repository, filtered_raw))
        for res in results:
            if res:
                valid_entries.append(res)

    print(f">>> [多仓体检] 探测完成，存活仓位: {len(valid_entries)} / {len(filtered_raw)} 个")

    # 智能保留核心主力双雄顺序（肥猫第1、饭太硬第2），随后无缝插入自建透明主仓
    feimao = next((u for u in valid_entries if "肥猫" in u.get("name", "")), None)
    fantaiying = next((u for u in valid_entries if "饭太硬" in u.get("name", "") and "主仓" in u.get("name", "")), None)
    
    other_entries = [
        u for u in valid_entries
        if u != feimao and u != fantaiying
    ]

    final_urls = []
    if feimao:
        final_urls.append(feimao)
    if fantaiying:
        final_urls.append(fantaiying)
    final_urls.append(SELF_HOSTED_TOP_ENTRY)
    final_urls.extend(other_entries)

    output_data = {
        "urls": final_urls,
        "lives": [
            {
                "name": "无水精选高可用电视与网络直播",
                "type": 0,
                "url": "https://tvbox.wushui.fun/tvboxlive.txt"
            }
        ]
    }
    with open(muti_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)

    print(f">>> [多仓体检] 多仓清洗与置顶集成完成，共写入 {len(final_urls)} 个高可用仓位 (已关联直播源)")
    return len(final_urls)

if __name__ == "__main__":
    target = os.path.abspath(os.path.join(os.path.dirname(__file__), "../tvboxmuti.json"))
    clean_and_integrate_muti_vod(target)
