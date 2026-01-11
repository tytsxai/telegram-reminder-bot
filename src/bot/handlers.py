"""处理器注册模块

将命令处理器和消息处理器注册到 Telegram Application。
"""

from telegram.ext import Application, CommandHandler as TGCommandHandler
from telegram.ext import MessageHandler, ConversationHandler, filters
from src.database.db import Database
from src.bot.commands import CommandHandler, DELETE_AWAITING_ID


def register_handlers(app: Application, db: Database) -> None:
    """注册所有处理器"""
    cmd = CommandHandler(db)

    app.add_handler(TGCommandHandler("start", cmd.start))
    app.add_handler(TGCommandHandler("help", cmd.help))
    app.add_handler(TGCommandHandler("remind", cmd.remind))
    app.add_handler(TGCommandHandler("list", cmd.list_reminders))

    # /delete 使用 ConversationHandler 支持分步输入
    delete_conv = ConversationHandler(
        entry_points=[TGCommandHandler("delete", cmd.delete_start)],
        states={
            DELETE_AWAITING_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cmd.delete_receive_id)
            ],
        },
        fallbacks=[TGCommandHandler("cancel", cmd.delete_cancel)],
        conversation_timeout=60,
    )
    app.add_handler(delete_conv)

    # 自然语言消息处理
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, cmd.handle_message))
