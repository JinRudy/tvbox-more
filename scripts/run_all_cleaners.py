#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/run_all_cleaners.py
TVBox 全自动化源治理总入口与熔断保护调度器
"""

import os
import sys

# 引入各个原子清洗模块
from cleaner_live import build_cleaned_live_channels
from builder_self_vod import build_self_hosted_vod
from cleaner_vod import clean_and_integrate_muti_vod

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

LIVE_FILE = os.path.join(BASE_DIR, "tvboxlive.txt")
VOD_FILE = os.path.join(BASE_DIR, "tvboxvod.json")
MUTI_FILE = os.path.join(BASE_DIR, "tvboxmuti.json")

# 安全熔断保护阈值（低于此阈值强行报错中断，严禁推送劣质残缺文件）
MIN_LIVE_CHANNELS = 60
MIN_VOD_SITES = 3
MIN_MUTI_REPOS = 10

def main():
    print("==================================================")
    print("🚀 [TVBox-Cleaner] 启动全自动化源治理与体检流水线")
    print("==================================================")

    # 1. 运行直播源清洗提纯
    print("\n--- 阶段 1: 直播源清洗、切片去广告与全网剧名挖掘 ---")
    live_count = build_cleaned_live_channels(LIVE_FILE)
    if live_count < MIN_LIVE_CHANNELS:
        print(f"❌ [熔断触发] 直播源存活数仅 {live_count}，低于安全底线 {MIN_LIVE_CHANNELS}！终止提交！")
        sys.exit(1)
    print(f"✅ 直播源阶段体检合格，存活数: {live_count}")

    # 2. 运行自建 100% 透明点播主仓构建
    print("\n--- 阶段 2: 全网开源 CMS 采集站《爱情公寓》基准压测与主仓构建 ---")
    vod_site_count = build_self_hosted_vod(VOD_FILE)
    if vod_site_count < MIN_VOD_SITES:
        print(f"❌ [熔断触发] 自建点播通过压测站点数仅 {vod_site_count}，低于安全底线 {MIN_VOD_SITES}！终止提交！")
        sys.exit(1)
    print(f"✅ 自建点播阶段体检合格，合格站点数: {vod_site_count}")

    # 3. 运行点播多仓健康检测与置顶集成
    print("\n--- 阶段 3: 点播多仓健康探测、死仓剔除与自建主仓置顶 ---")
    muti_count = clean_and_integrate_muti_vod(MUTI_FILE)
    if muti_count < MIN_MUTI_REPOS:
        print(f"❌ [熔断触发] 多仓存活数仅 {muti_count}，低于安全底线 {MIN_MUTI_REPOS}！终止提交！")
        sys.exit(1)
    print(f"✅ 点播多仓阶段体检合格，存活仓位数: {muti_count}")

    print("\n==================================================")
    print("🎉 [TVBox-Cleaner] 全部治理阶段圆满完成，健康指标全部达标！")
    print("==================================================")

if __name__ == "__main__":
    main()
