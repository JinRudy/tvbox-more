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

    def test_cloud_token_reference(self):
        """测试包含统一云端免扫码 Token 引用"""
        token_ref = self.data.get("token") or self.data.get("token_url")
        self.assertTrue(
            token_ref and "tvbox.wushui.fun/token.json" in token_ref,
            "必须包含指向云端 tvbox.wushui.fun/token.json 的免扫码配置"
        )

if __name__ == "__main__":
    unittest.main()
