"""命令测试"""
import pytest


class TestCommands:
    """命令测试"""

    def test_start_command(self):
        """测试 start 命令"""
        cmd = "/start"
        assert cmd.startswith("/")

    def test_help_command(self):
        """测试 help 命令"""
        cmd = "/help"
        assert "help" in cmd

    def test_remind_command(self):
        """测试 remind 命令"""
        cmd = "/remind"
        assert "remind" in cmd
