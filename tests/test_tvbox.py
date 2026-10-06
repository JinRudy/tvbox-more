import json
import os
import re
import unittest
from urllib.parse import urlparse

class TestTVBoxMultiConfig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../tvboxmuti.json")
        )
        with open(cls.config_path, "r", encoding="utf-8") as f:
            cls.data = json.load(f)

    def test_file_exists_and_is_valid_json(self):
        """测试配置文件存在且为合法 JSON"""
        self.assertTrue(os.path.exists(self.config_path))
        self.assertIsInstance(self.data, dict)

    def test_urls_structure_and_completeness(self):
        """测试 urls 列表的完整性与条目格式"""
        self.assertIn("urls", self.data, "多仓配置必须包含 'urls' 字段")
        urls = self.data["urls"]
        self.assertIsInstance(urls, list)
        self.assertGreaterEqual(len(urls), 20, "有效多仓源数量不应少于 20 条")

        seen_urls = set()
        for idx, item in enumerate(urls):
            self.assertIn("name", item, f"第 {idx} 项缺少 'name' 字段")
            self.assertIn("url", item, f"第 {idx} 项缺少 'url' 字段")
            self.assertIsInstance(item["name"], str)
            self.assertIsInstance(item["url"], str)
            self.assertTrue(item["name"].strip(), f"第 {idx} 项 'name' 不能为空")
            
            raw_url = item["url"].strip()
            self.assertTrue(
                raw_url.startswith("http://") or raw_url.startswith("https://"),
                f"URL 格式不合法: {raw_url}"
            )
            # 校验无重复 URL
            self.assertNotIn(raw_url, seen_urls, f"发现重复的源 URL: {raw_url}")
            seen_urls.add(raw_url)

            # 校验域名不含未转码的中文字符（应转为 punycode）
            parsed = urlparse(raw_url)
            self.assertFalse(
                re.search(r'[\u4e00-\u9fa5]', parsed.netloc),
                f"域名包含中文字符，应转换为 Punycode: {parsed.netloc}"
            )

    def test_lives_structure_and_completeness(self):
        """测试根节点 lives 直播源定义"""
        self.assertIn("lives", self.data, "混合多仓配置必须包含 'lives' 直播源字段")
        lives = self.data["lives"]
        self.assertIsInstance(lives, list)
        self.assertGreaterEqual(len(lives), 1, "lives 列表不能为空")

        for idx, item in enumerate(lives):
            self.assertIn("name", item, f"直播项 {idx} 缺少 'name'")
            self.assertIn("url", item, f"直播项 {idx} 缺少 'url'")
            self.assertIn("type", item, f"直播项 {idx} 缺少 'type'")
            self.assertIsInstance(item["type"], int)
            raw_url = item["url"].strip()
            self.assertTrue(
                raw_url.startswith("http://") or raw_url.startswith("https://"),
                f"直播 URL 格式不合法: {raw_url}"
            )

    def test_core_sources_coverage(self):
        """测试核心主流源的覆盖情况"""
        urls = self.data.get("urls", [])
        names = [item.get("name", "") for item in urls]
        all_names_str = " ".join(names)
        
        # 验证核心标志性源存在
        self.assertTrue(
            any("饭太硬" in n for n in names),
            f"应包含饭太硬相关源，当前源列表: {all_names_str}"
        )
        self.assertTrue(
            any("肥猫" in n for n in names),
            f"应包含肥猫相关源，当前源列表: {all_names_str}"
        )

if __name__ == "__main__":
    unittest.main()
