"""处理器注册模块

将命令处理器和消息处理器注册到 Telegram Application。
"""

from telegram.ext import Application, CommandHandler as TGCommandHandler
from telegram.ext import MessageHandler, filters
from src.database.db import Database
from src.bot.commands import CommandHandler


def register_handlers(app: Application, db: Database) -> None:
    """注册所有处理器"""
    cmd = CommandHandler(db)

    app.add_handler(TGCommandHandler("start", cmd.start))
    app.add_handler(TGCommandHandler("help", cmd.help))
    app.add_handler(TGCommandHandler("remind", cmd.remind))
    app.add_handler(TGCommandHandler("list", cmd.list_reminders))
    app.add_handler(TGCommandHandler("delete", cmd.delete))

    # 自然语言消息处理
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, cmd.handle_message))
