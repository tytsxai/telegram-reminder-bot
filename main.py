"""智能提醒机器人入口"""

import asyncio
import logging
from telegram.ext import Application
from src.config import settings
from src.database.db import Database
from src.bot.handlers import register_handlers
from src.services.scheduler import SchedulerService

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# 全局数据库实例
db = Database()
scheduler = None


async def send_reminder(chat_id: int, message: str):
    """发送提醒消息的回调函数"""
    global app
    await app.bot.send_message(chat_id=chat_id, text=message)


async def post_init(application: Application):
    """应用初始化后的回调"""
    global scheduler
    await db.init_db()
    logger.info("Database initialized")

    scheduler = SchedulerService(db, send_reminder)
    scheduler.start()
    logger.info("Scheduler started")


async def main():
    """主函数"""
    global app
    if not settings.BOT_TOKEN:
        logger.error("BOT_TOKEN not configured")
        return

    app = Application.builder().token(settings.BOT_TOKEN).post_init(post_init).build()
    register_handlers(app, db)

    logger.info("Bot starting...")
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
