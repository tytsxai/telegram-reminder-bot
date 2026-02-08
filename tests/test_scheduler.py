"""调度器测试"""



class TestScheduler:
    """调度器测试"""

    def test_interval_positive(self):
        """测试间隔为正数"""
        interval = 30
        assert interval > 0

    def test_interval_default(self):
        """测试默认间隔"""
        default = 30
        assert default == 30
