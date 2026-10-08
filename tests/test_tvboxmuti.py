import os
import json
import unittest

class TestTVBoxMutiConfig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.muti_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../tvboxmuti.json")
        )
        cls.data = {}
        if os.path.exists(cls.muti_path):
            with open(cls.muti_path, "r", encoding="utf-8") as f:
                cls.data = json.load(f)

    def test_file_exists_and_valid_json(self):
        """测试 tvboxmuti.json 存在且为合法 JSON"""
        self.assertTrue(os.path.exists(self.muti_path), "tvboxmuti.json 必须存在")
        self.assertIn("urls", self.data, "必须包含 urls 字段")
        self.assertIsInstance(self.data["urls"], list, "urls 必须是列表")

    def test_top_self_hosted_vod_entry(self):
        """测试多仓前列收录了我们自建的 100% 透明零黑匣子主仓，且绑定了 lives"""
        urls = self.data.get("urls", [])
        self.assertGreater(len(urls), 2, "多仓列表不应为空")
        top3_names = [u.get("name", "") for u in urls[:3]]
        self.assertTrue(
            any("自建" in n for n in top3_names),
            f"前3位中必须收录自建透明主仓，当前为: {top3_names}"
        )
        # 验证关联了我们的直播源
        lives = self.data.get("lives", [])
        self.assertGreater(len(lives), 0, "必须包含关联的 lives 直播源")
        self.assertIn("tvboxlive.txt", lives[0].get("url", ""))

    def test_preserved_genres_and_no_dead_urls(self):
        """测试保留了原有多仓主要分类，且没有明显广告引流"""
        urls = self.data.get("urls", [])
        names = [u.get("name", "") for u in urls]
        name_str = " ".join(names)
        
        # 验证核心分类保留
        self.assertIn("精选主力", name_str)
        self.assertIn("体育", name_str)
        self.assertIn("综合影视", name_str)

        for u in urls:
            url_val = u.get("url", "")
            name_val = u.get("name", "")
            self.assertTrue(url_val.startswith("http"), f"仓位必须是合法 http/https 链接: {u}")
            self.assertNotIn("免费订阅", name_val)
            self.assertNotIn("加群", name_val)

if __name__ == "__main__":
    unittest.main()
