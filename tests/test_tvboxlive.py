import os
import unittest

class TestTVBoxLiveConfig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../tvboxlive.txt")
        )
        cls.content = ""
        if os.path.exists(cls.live_path):
            with open(cls.live_path, "r", encoding="utf-8") as f:
                cls.content = f.read()

    def test_file_exists_and_not_empty(self):
        """测试 tvboxlive.txt 存在且内容充沛"""
        self.assertTrue(os.path.exists(self.live_path), "tvboxlive.txt 必须存在")
        self.assertGreater(len(self.content), 1000, "直播源内容不应少于 1000 字符")

    def test_standard_genre_format(self):
        """测试标准 #genre# 分类格式与频道格式"""
        lines = self.content.splitlines()
        genres = [l.strip() for l in lines if "#genre#" in l]
        self.assertGreaterEqual(len(genres), 6, "至少应包含 6 个核心分组")
        
        # 验证核心类别存在
        genre_text = "".join(genres)
        self.assertIn("央视", genre_text)
        self.assertIn("卫视", genre_text)
        self.assertIn("体育", genre_text)
        self.assertTrue("虎牙" in genre_text or "轮播" in genre_text)
        self.assertTrue("国际" in genre_text or "港澳台" in genre_text)

        # 验证没有广告假台
        for l in lines:
            self.assertNotIn("免費訂閲", l, "严禁包含免費訂閲假频道")
            self.assertNotIn("維護時間", l, "严禁包含維護時間假频道")

    def test_international_and_proxy_channels(self):
        """测试包含外国与国际频道，且正确配置代理"""
        self.assertTrue(
            any(k in self.content for k in ["凤凰", "翡翠", "TVB", "CGTN", "BBC", "CNN", "DW", "NHK"]),
            "必须包含知名国际或港澳台频道"
        )
        # 验证包含基于 Cloudflare 的代理转发链接
        self.assertIn("tvbox.wushui.fun/proxy?url=", self.content, "必须包含针对海外受限频道的云端代理链接")

    def test_no_crash_characters_and_fake_mp4(self):
        """测试严禁包含导致电视盒子解析截断的字符和假短视频"""
        lines = self.content.splitlines()
        for l in lines:
            if "," in l and not "#genre#" in l:
                _, url = l.strip().split(",", 1)
                self.assertNotIn("[", url, f"严禁包含 IPv6 方括号导致安卓解析崩溃: {url}")
                self.assertNotIn("]", url, f"严禁包含 IPv6 方括号导致安卓解析崩溃: {url}")
                self.assertNotIn("%2C", url, f"严禁包含逗号转码字符导致 TVBox 切割截断: {url}")
                self.assertFalse(url.endswith(".mp4"), f"严禁包含 mp4 录像假台: {url}")
                self.assertNotIn("kwimgs", url, f"严禁包含快手短视频假台: {url}")
                self.assertLessEqual(len(url), 230, f"URL 过长可能导致低配电视内存溢出: {url}")
                # 严格禁止已知的广告垫片 VPS IP
                for fake_ip in ["74.91.26.", "63.141.230.", "38.75.136."]:
                    self.assertNotIn(fake_ip, url, f"严禁包含切片404广告垫片假VPS: {url}")

    def test_minimum_channel_count(self):
        """测试存活频道数量门禁 (防熔断)"""
        channel_lines = [l for l in self.content.splitlines() if "," in l and not "#genre#" in l]
        self.assertGreaterEqual(len(channel_lines), 60, f"总频道数不应少于 60，当前仅 {len(channel_lines)}")

if __name__ == "__main__":
    unittest.main()
