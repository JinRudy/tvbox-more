import os
import json
import unittest

class TestTVBoxVodConfig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vod_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../tvboxvod.json")
        )
        cls.data = {}
        if os.path.exists(cls.vod_path):
            with open(cls.vod_path, "r", encoding="utf-8") as f:
                cls.data = json.load(f)

    def test_file_exists_and_valid_json(self):
        """测试自建点播主仓 tvboxvod.json 存在且为合法 JSON"""
        self.assertTrue(os.path.exists(self.vod_path), "tvboxvod.json 必须存在")
        self.assertIsInstance(self.data, dict, "根节点必须是 JSON Object")

    def test_sites_exist_and_zero_blackbox(self):
        """测试 100% 纯净开源原生协议 (零黑匣子 spider.jar)"""
        sites = self.data.get("sites", [])
        self.assertGreaterEqual(len(sites), 3, "经过《爱情公寓》压测后至少保留 3 个高质量开源站点")
        
        # 验证每个站点都是原生 type: 1，绝不依赖第三方神秘 jar
        for s in sites:
            self.assertEqual(s.get("type"), 1, f"必须是 TVBox 原生开源 JSON CMS 协议(type: 1): {s.get('name')}")
            self.assertTrue(s.get("api", "").startswith("http"), f"API 必须是有效 HTTP/HTTPS 地址: {s}")
            self.assertEqual(s.get("searchable"), 1, "所有站点必须支持搜索")
            self.assertNotIn("免费订阅", s.get("name", ""))
            self.assertNotIn("加群", s.get("name", ""))

    def test_pure_opensource_no_token_leak(self):
        """测试 100% 开源直链纯净化点播主仓，不依赖且不泄露个人敏感网盘 Token"""
        token_val = self.data.get("token") or ""
        open_token_val = self.data.get("open_token") or ""
        self.assertFalse(token_val.startswith("http://") or token_val.startswith("https://"), "纯净主仓不应外挂公开网盘 Token 引用")
        self.assertEqual(open_token_val, "", "严禁在点播主仓泄露个人 Open Token")

    def test_valid_spider_jar(self):
        """测试 TVBox 核心必经 Dex Spider Jar 存在且配置完整 (防 Jar包解析失败 报错)"""
        spider = self.data.get("spider") or ""
        self.assertTrue(len(spider) > 10, "必须配置有效的 spider jar 路径，严禁为空字符串导致 TVBox 解析崩溃")
        self.assertIn(";md5;", spider, "spider 配置必须包含标准 MD5 完整性校验")
        jar_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../jar/fan.txt"))
        self.assertTrue(os.path.exists(jar_path), "自建托管的 jar/fan.txt 必须存在于仓库中")
        self.assertGreater(os.path.getsize(jar_path), 500000, "自建 jar 文件体积必须正常 (>500KB)")

if __name__ == "__main__":
    unittest.main()
