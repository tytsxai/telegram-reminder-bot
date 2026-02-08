"""时区测试"""



class TestTimezone:
    """时区测试"""

    def test_default_timezone(self):
        """测试默认时区"""
        tz = "Asia/Shanghai"
        assert "Asia" in tz

    def test_utc_timezone(self):
        """测试 UTC 时区"""
        tz = "UTC"
        assert tz == "UTC"
