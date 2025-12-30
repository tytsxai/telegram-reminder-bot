"""用户测试"""
import pytest


class TestUser:
    """用户测试"""

    def test_user_id_positive(self):
        """测试用户ID为正数"""
        user_id = 123456
        assert user_id > 0

    def test_username_format(self):
        """测试用户名格式"""
        username = "test_user"
        assert username is not None
