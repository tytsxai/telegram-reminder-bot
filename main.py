"""智能提醒机器人入口"""

import logging
from telegram.ext import Application
from src.config import settings
from src.database.db import Database
from src.bot.handlers import register_handlers
from src.services.scheduler import SchedulerService
from src.services.healthcheck import HealthCheckServer
from src.utils.instance_lock import InstanceLock


def setup_logging() -> None:
    """配置日志输出"""
    level_name = (settings.LOG_LEVEL or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=level
    )


setup_logging()
logger = logging.getLogger(__name__)

# 全局数据库实例
db = Database()
scheduler = None
health_server = None
instance_lock = None


async def send_reminder(chat_id: int, message: str):
    """发送提醒消息的回调函数"""
    global app
    await app.bot.send_message(chat_id=chat_id, text=message)


async def post_init(application: Application):
    """应用初始化后的回调"""
    global scheduler, health_server
    await db.init_db()
    logger.info("Database initialized")

    scheduler = SchedulerService(db, send_reminder)
    scheduler.start()
    logger.info("Scheduler started")

    if settings.HEALTHCHECK_ENABLED:

        async def _health_check():
            ok = await db.ping()
            return {"ok": ok, "status": "ok" if ok else "db_error"}

        health_server = HealthCheckServer(
            host=settings.HEALTHCHECK_HOST,
            port=settings.HEALTHCHECK_PORT,
            path=settings.HEALTHCHECK_PATH,
            check=_health_check,
        )
        await health_server.start()
        logger.info("Healthcheck started")


async def post_shutdown(application: Application):
    """应用关闭后的回调"""
    global scheduler, health_server, instance_lock
    if scheduler:
        scheduler.stop()
        scheduler = None
    if health_server:
        await health_server.stop()
        health_server = None
    if instance_lock:
        instance_lock.release()
        instance_lock = None


def main():
    """主函数"""
    global app, instance_lock
    if not settings.BOT_TOKEN:
        logger.error("BOT_TOKEN not configured")
        return

    if settings.INSTANCE_LOCK_ENABLED:
        instance_lock = InstanceLock(settings.INSTANCE_LOCK_PATH)
        if not instance_lock.acquire():
            logger.error("Another instance is running. Exiting.")
            return

    app = (
        Application.builder()
        .token(settings.BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    register_handlers(app, db)

    logger.info("Bot starting...")
    try:
        app.run_polling()
    finally:
        if instance_lock:
            instance_lock.release()
            instance_lock = None


if __name__ == "__main__":
    main()
