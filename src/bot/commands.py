"""命令处理模块

处理 Telegram Bot 命令和自然语言消息：
- /start, /help: 欢迎与帮助
- /remind: 设置提醒
- /list: 查看提醒列表（支持分页）
- /delete: 删除提醒
- 自然语言消息自动解析
"""

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from src.database.db import Database
from src.models.reminder import RepeatType
from src.services.ai_parser import get_default_parser
from src.services.reminder import ReminderService
from src.utils.text_utils import truncate_utf16, utf16_length

# ConversationHandler 状态
DELETE_AWAITING_ID = 1

logger = logging.getLogger(__name__)


class CommandHandler:
    """命令处理器"""

    _DEFAULT_PAGE_SIZE = 20
    _MAX_PAGE_SIZE = 200

    def __init__(self, db: Database):
        self.db = db
        self.reminder_service = ReminderService(db)
        self.parser = get_default_parser()

    def _format_repeat(self, reminder) -> str:
        if reminder.repeat_type == RepeatType.NONE:
            return "不重复"
        if reminder.repeat_type == RepeatType.DAILY:
            return "每天"
        if reminder.repeat_type == RepeatType.WEEKLY:
            weekday_map = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            if (
                reminder.repeat_weekday is not None
                and 0 <= reminder.repeat_weekday <= 6
            ):
                return f"每周{weekday_map[reminder.repeat_weekday]}"
            return "每周"
        if reminder.repeat_type == RepeatType.MONTHLY:
            day = reminder.repeat_monthday or reminder.remind_at.day
            return f"每月{day}号"
        return "不重复"

    async def _reply(self, update: Update, text: str) -> None:
        message = update.effective_message or update.message
        if message:
            await message.reply_text(text)

    def _build_created_reply(self, reminder) -> str:
        header = "✅ 提醒已创建！\n内容: "
        footer = f"\n时间: {reminder.remind_at.strftime('%Y-%m-%d %H:%M')}"
        max_len = 4096
        available = max_len - utf16_length(header) - utf16_length(footer)
        safe_content = truncate_utf16(reminder.content, max(0, available), suffix="...")
        return f"{header}{safe_content}{footer}"

    async def _reply_chunks(
        self, update: Update, header: str, entries: list[str], max_len: int = 4096
    ) -> None:
        if not entries:
            await self._reply(update, header)
            return
        max_entry_len = max(0, max_len - utf16_length(header) - 1)
        chunks: list[str] = []
        current = header
        for entry in entries:
            safe_entry = truncate_utf16(entry, max_entry_len, suffix="...")
            candidate = f"{current}\n{safe_entry}"
            if utf16_length(candidate) > max_len and current != header:
                chunks.append(current)
                current = f"{header}\n{safe_entry}"
            elif utf16_length(candidate) > max_len:
                chunks.append(header)
                current = f"{header}\n{safe_entry}"
            else:
                current = candidate
        if current:
            chunks.append(current)
        for chunk in chunks:
            await self._reply(update, chunk)

    def _get_user_chat_ids(self, update: Update):
        user = update.effective_user
        chat = update.effective_chat
        if not user or not chat:
            return None
        return user.id, chat.id

    async def _parse_text(self, text: str):
        try:
            return await asyncio.to_thread(self.parser.parse, text)
        except Exception as exc:
            logger.exception("Parse failed: %s", exc)
            return None

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /start 命令"""
        await self._reply(
            update,
            "👋 欢迎使用智能提醒机器人！\n\n"
            "命令列表：\n"
            "/remind <内容> - 设置提醒\n"
            "/list [页码] [每页数量] - 查看提醒列表\n"
            "/delete <ID> - 删除提醒（也可直接 /delete 交互输入）\n"
            "/help - 获取帮助",
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /help 命令"""
        await self._reply(
            update,
            "📖 使用帮助\n\n"
            "命令示例：\n"
            "• /list 1\n"
            "• /list 2 50\n"
            "• /delete 1（或 /delete 后输入 ID）\n\n"
            "自然语言示例：\n"
            "• 明天上午9点提醒我开会\n"
            "• 每天8点提醒我喝水\n"
            "• 每周一8点提醒我开会\n"
            "• 每月1号8点提醒我交房租\n"
            "• 后天下午3点提醒我买菜",
        )

    async def remind(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /remind 命令"""
        ids = self._get_user_chat_ids(update)
        if not ids:
            await self._reply(update, "⚠️ 仅支持私聊或群聊用户消息")
            return
        user_id, chat_id = ids
        if not context.args:
            await self._reply(update, "请输入提醒内容")
            return

        text = " ".join(context.args)
        # AI 解析可能触发阻塞式 HTTP，放到线程池避免卡住事件循环。
        result = await self._parse_text(text)

        if result is None:
            await self._reply(
                update, "无法解析时间，请使用格式：\n" "明天9点提醒我开会"
            )
            return

        try:
            reminder = await self.reminder_service.create_reminder(
                user_id=user_id,
                chat_id=chat_id,
                content=result.content,
                remind_at=result.remind_at,
                repeat_type=result.repeat_type,
                repeat_weekday=result.repeat_weekday,
                repeat_monthday=result.repeat_monthday,
            )
        except Exception as exc:
            logger.exception(
                "Failed to create reminder user_id=%s chat_id=%s: %s",
                user_id,
                chat_id,
                exc,
            )
            await self._reply(update, "⚠️ 系统繁忙，请稍后再试")
            return

        await self._reply(update, self._build_created_reply(reminder))

    async def list_reminders(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """处理 /list 命令（支持分页）"""
        ids = self._get_user_chat_ids(update)
        if not ids:
            await self._reply(update, "⚠️ 仅支持私聊或群聊用户消息")
            return
        user_id, chat_id = ids
        page = 1
        page_size = self._DEFAULT_PAGE_SIZE
        if context.args:
            try:
                page = int(context.args[0])
            except ValueError:
                await self._reply(update, "页码必须是数字")
                return
            if page <= 0:
                await self._reply(update, "页码必须大于 0")
                return
            if len(context.args) > 1:
                try:
                    page_size = int(context.args[1])
                except ValueError:
                    await self._reply(update, "每页数量必须是数字")
                    return
                if not (1 <= page_size <= self._MAX_PAGE_SIZE):
                    await self._reply(
                        update, f"每页数量必须在 1 到 {self._MAX_PAGE_SIZE} 之间"
                    )
                    return
        try:
            reminders = await self.reminder_service.get_user_reminders(
                user_id, chat_id, limit=page_size + 1, offset=(page - 1) * page_size
            )
        except Exception as exc:
            logger.exception(
                "Failed to list reminders user_id=%s chat_id=%s: %s",
                user_id,
                chat_id,
                exc,
            )
            await self._reply(update, "⚠️ 系统繁忙，请稍后再试")
            return

        if not reminders:
            await self._reply(update, f"📭 暂无提醒（第 {page} 页）")
            return

        has_more = len(reminders) > page_size
        if has_more:
            reminders = reminders[:page_size]

        entries = []
        for r in reminders:
            entries.append(
                f"[{r.id}] {r.content}\n"
                f"    ⏰ {r.remind_at.strftime('%Y-%m-%d %H:%M')} | 🔁 {self._format_repeat(r)}"
            )
        if has_more:
            entries.append(f"更多: /list {page + 1}")

        await self._reply_chunks(update, f"📋 提醒列表（第 {page} 页）：", entries)

    async def delete_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """处理 /delete 命令入口"""
        ids = self._get_user_chat_ids(update)
        if not ids:
            await self._reply(update, "⚠️ 仅支持私聊或群聊用户消息")
            return ConversationHandler.END

        # 如果带参数，直接执行删除
        if context.args:
            return await self._do_delete(update, context.args[0])

        await self._reply(update, "请输入提醒ID")
        return DELETE_AWAITING_ID

    async def delete_receive_id(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """接收用户输入的提醒 ID"""
        message = update.effective_message or update.message
        if not message or not message.text:
            return ConversationHandler.END
        return await self._do_delete(update, message.text.strip())

    async def delete_cancel(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """取消删除操作"""
        await self._reply(update, "已取消删除操作")
        return ConversationHandler.END

    async def _do_delete(self, update: Update, id_text: str) -> int:
        """执行删除逻辑"""
        ids = self._get_user_chat_ids(update)
        if not ids:
            await self._reply(update, "⚠️ 仅支持私聊或群聊用户消息")
            return ConversationHandler.END
        user_id, chat_id = ids

        try:
            reminder_id = int(id_text)
        except ValueError:
            await self._reply(update, "ID必须是数字")
            return ConversationHandler.END

        try:
            result = await self.reminder_service.delete_reminder_by_user(
                reminder_id, user_id, chat_id
            )
        except Exception as exc:
            logger.exception(
                "Failed to delete reminder id=%s user_id=%s chat_id=%s: %s",
                reminder_id,
                user_id,
                chat_id,
                exc,
            )
            await self._reply(update, "⚠️ 系统繁忙，请稍后再试")
            return ConversationHandler.END

        if result:
            await self._reply(update, "✅ 提醒已删除")
        else:
            await self._reply(update, "❌ 提醒不存在或无权删除")
        return ConversationHandler.END

    async def handle_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """处理自然语言消息"""
        ids = self._get_user_chat_ids(update)
        if not ids:
            await self._reply(update, "⚠️ 仅支持私聊或群聊用户消息")
            return
        user_id, chat_id = ids
        message = update.effective_message or update.message
        if not message or not getattr(message, "text", None):
            return
        text = message.text
        # AI 解析可能触发阻塞式 HTTP，放到线程池避免卡住事件循环。
        result = await self._parse_text(text)

        if result is None:
            await self._reply(update, "💡 试试这样说：\n" "明天9点提醒我开会")
            return

        try:
            reminder = await self.reminder_service.create_reminder(
                user_id=user_id,
                chat_id=chat_id,
                content=result.content,
                remind_at=result.remind_at,
                repeat_type=result.repeat_type,
                repeat_weekday=result.repeat_weekday,
                repeat_monthday=result.repeat_monthday,
            )
        except Exception as exc:
            logger.exception(
                "Failed to create reminder user_id=%s chat_id=%s: %s",
                user_id,
                chat_id,
                exc,
            )
            await self._reply(update, "⚠️ 系统繁忙，请稍后再试")
            return

        await self._reply(update, self._build_created_reply(reminder))
