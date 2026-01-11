"""Bot测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from src.database.db import Database
from src.bot.commands import CommandHandler


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def db(db_path):
    return Database(db_path)


@pytest.fixture
def mock_update():
    update = MagicMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    update.message.text = ""
    update.effective_message = update.message
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    update.effective_chat = MagicMock()
    update.effective_chat.id = 456
    return update


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.args = []
    return context


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch):
    fixed = datetime(2025, 1, 1, 8, 0, 0)
    monkeypatch.setattr(
        "src.services.ai_parser.RuleBasedParser._get_now", lambda self: fixed
    )
    # 强制使用 RuleBasedParser，避免 AI API 调用
    monkeypatch.setattr("src.config.settings.AI_API_KEY", None)
    monkeypatch.setattr("src.config.settings.OPENAI_API_KEY", None)
    monkeypatch.setattr("src.config.settings.ANTHROPIC_API_KEY", None)
    monkeypatch.setattr("src.config.settings.AI_PROVIDER", None)
    return fixed


class TestCommandHandler:
    """CommandHandler 测试"""

    @pytest.mark.asyncio
    async def test_start(self, db, mock_update, mock_context):
        await db.init_db()
        cmd = CommandHandler(db)
        await cmd.start(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_help(self, db, mock_update, mock_context):
        await db.init_db()
        cmd = CommandHandler(db)
        await cmd.help(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_remind_no_args(self, db, mock_update, mock_context):
        await db.init_db()
        cmd = CommandHandler(db)
        mock_context.args = []
        await cmd.remind(mock_update, mock_context)
        mock_update.message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_remind_success(self, db, mock_update, mock_context):
        await db.init_db()
        cmd = CommandHandler(db)
        mock_context.args = ["明天", "9点", "提醒我", "开会"]
        await cmd.remind(mock_update, mock_context)
        mock_update.message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_remind_invalid_time(self, db, mock_update, mock_context):
        await db.init_db()
        cmd = CommandHandler(db)
        mock_context.args = ["提醒我", "开会"]
        await cmd.remind(mock_update, mock_context)
        mock_update.message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_list_empty(self, db, mock_update, mock_context):
        await db.init_db()
        cmd = CommandHandler(db)
        await cmd.list_reminders(mock_update, mock_context)
        mock_update.message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_list_with_reminders(self, db, mock_update, mock_context):
        await db.init_db()
        cmd = CommandHandler(db)
        mock_context.args = ["今天", "9点", "提醒我", "测试"]
        await cmd.remind(mock_update, mock_context)
        mock_update.message.reply_text.reset_mock()
        await cmd.list_reminders(mock_update, mock_context)
        mock_update.message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_delete_no_args(self, db, mock_update, mock_context):
        await db.init_db()
        cmd = CommandHandler(db)
        mock_context.args = []
        await cmd.delete_start(mock_update, mock_context)
        mock_update.message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_delete_invalid_id(self, db, mock_update, mock_context):
        await db.init_db()
        cmd = CommandHandler(db)
        mock_context.args = ["abc"]
        await cmd.delete_start(mock_update, mock_context)
        mock_update.message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_delete_not_found(self, db, mock_update, mock_context):
        await db.init_db()
        cmd = CommandHandler(db)
        mock_context.args = ["999"]
        await cmd.delete_start(mock_update, mock_context)
        mock_update.message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_delete_success(self, db, mock_update, mock_context):
        await db.init_db()
        cmd = CommandHandler(db)
        # 先创建一个提醒
        mock_context.args = ["今天", "9点", "提醒我", "删除测试"]
        await cmd.remind(mock_update, mock_context)
        # 删除
        mock_context.args = ["1"]
        mock_update.message.reply_text.reset_mock()
        await cmd.delete_start(mock_update, mock_context)
        mock_update.message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_handle_message_success(self, db, mock_update, mock_context):
        await db.init_db()
        cmd = CommandHandler(db)
        mock_update.message.text = "明天9点提醒我开会"
        await cmd.handle_message(mock_update, mock_context)
        mock_update.message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_handle_message_invalid(self, db, mock_update, mock_context):
        await db.init_db()
        cmd = CommandHandler(db)
        mock_update.message.text = "你好"
        await cmd.handle_message(mock_update, mock_context)
        mock_update.message.reply_text.assert_called()


class TestRegisterHandlers:
    """register_handlers 测试"""

    def test_register_handlers(self, db):
        """测试处理器注册"""
        from src.bot.handlers import register_handlers

        app = MagicMock()
        app.add_handler = MagicMock()

        register_handlers(app, db)

        # 验证注册了6个处理器（4个命令 + 1个会话 + 1个消息处理器）
        assert app.add_handler.call_count == 6
