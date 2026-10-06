# TVBox 聚合多仓与高可用直播源配置

本仓库维护了一套针对 **TVBox、影视仓、OK影音** 等播放器的高可用混合配置文件（多仓点播 + 全局电视直播源）。

---

## 🌟 核心特性

1. **多仓 + 直播混合支持 (Hybrid Config)**：
   - 包含 **40+ 条** 并发测活可用的精选多仓源（饭太硬全系、肥猫、王二小、俊于、高天流云、体育专线、少儿动漫等）；
   - 根节点内置 **4 组** 高可用全国央视/卫视直播源（支持 IPv6/IPv4 自适应、4K 超清、EPG 电视节目单与高清台标）。
2. **全自动化测活与死链剔除**：
   - 内置并发健康检测脚本，自动剔除 404、401、证书失效及超时死链；
   - 自动将中文域名转换为 Punycode，保证老旧电视盒子的 WebKit 解析兼容性。
3. **清晰的分组与分类编排**：
   - `⭐[精选主力]`：饭太硬、肥猫、王二小、胖鸭、俊于等主线仓
   - `⚽[体育专线]`：东篱体育、高天JSM体育、小马体育等
   - `👶[少儿动漫]`：夜猫少儿、动漫城等
   - `🎬[综合影视]`：30 余条各类高画质影视聚合线路
   - `📦[综合多仓]`：整合各大多仓入口
   - `📡[电视专线]`：即使在不支持根级 lives 的极老旧盒子上，也可在多仓列表中一键切换至纯直播专线。

---

## 🚀 使用方法

在 TVBox 或影视仓等播放器的 **【设置】 -> 【配置地址】** 中填入以下直链（根据你的托管方式）：

```text
https://raw.githubusercontent.com/JinRudy/tvbox-more/main/tvboxmuti.json
```

或使用 GitHub 加速镜像：

```text
https://gh-proxy.com/https://raw.githubusercontent.com/JinRudy/tvbox-more/main/tvboxmuti.json
```

---

## 🛠️ 维护与自动更新

本项目包含完整的自动化检测与测试套件：

### 1. 运行自动化测活与生成
```bash
python3 scripts/audit_and_generate.py
```

### 2. 运行配置合规性单元测试
```bash
python3 -m unittest tests/test_tvbox.py
```
