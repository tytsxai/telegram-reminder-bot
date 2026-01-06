"""智能提醒机器人入口"""

import logging
from telegram.ext import Application, ContextTypes
from telegram import BotCommand
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


def log_startup_settings() -> None:
    """记录关键配置（不包含敏感信息）。"""
    logger.info(
        "Config: timezone=%s db_path=%s scheduler_interval=%s batch=%s lock=%s concurrency=%s",
        settings.TIMEZONE,
        settings.DATABASE_PATH,
        settings.SCHEDULER_INTERVAL_SECONDS,
        settings.SCHEDULER_BATCH_SIZE,
        settings.SCHEDULER_LOCK_SECONDS,
        settings.SCHEDULER_SEND_CONCURRENCY,
    )
    logger.info(
        "Update handling: drop_pending_updates=%s",
        settings.DROP_PENDING_UPDATES,
    )
    if settings.HEALTHCHECK_ENABLED:
        logger.info(
            "Healthcheck enabled: host=%s port=%s path=%s",
            settings.HEALTHCHECK_HOST,
            settings.HEALTHCHECK_PORT,
            settings.HEALTHCHECK_PATH,
        )
    else:
        logger.info("Healthcheck disabled")
    logger.info(
        "Instance lock: enabled=%s path=%s",
        settings.INSTANCE_LOCK_ENABLED,
        settings.INSTANCE_LOCK_PATH,
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

    try:
        await application.bot.set_my_commands(
            [
                BotCommand("start", "启动机器人"),
                BotCommand("help", "使用帮助"),
                BotCommand("remind", "设置提醒"),
                BotCommand("list", "查看提醒列表"),
                BotCommand("delete", "删除提醒"),
            ]
        )
        logger.info("Bot commands registered")
    except Exception as exc:
        logger.warning("Failed to register bot commands: %s", exc)

    scheduler = SchedulerService(db, send_reminder)
    scheduler.start()
    logger.info("Scheduler started")

    if settings.HEALTHCHECK_ENABLED:

        async def _health_check():
            # 同时检查 DB 与调度器，避免“进程活着但不工作”的情况。
            db_ok = await db.ping()
            scheduler_ok = scheduler.is_healthy() if scheduler else False
            ok = db_ok and scheduler_ok
            if not db_ok:
                status = "db_error"
            elif not scheduler_ok:
                status = "scheduler_unhealthy"
            else:
                status = "ok"
            payload = {
                "ok": ok,
                "status": status,
                "db_ok": db_ok,
                "scheduler_ok": scheduler_ok,
                "scheduler": scheduler.health_snapshot() if scheduler else None,
            }
            return payload

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


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """统一错误处理，避免异常导致请求无响应。"""
    logger.exception("Unhandled error: %s", context.error)
    message = getattr(update, "effective_message", None)
    if message:
        try:
            await message.reply_text("⚠️ 系统繁忙，请稍后再试")
        except Exception:
            pass


def main():
    """主函数"""
    global app, instance_lock
    if not settings.BOT_TOKEN:
        logger.error("BOT_TOKEN not configured")
        # Fail fast so process supervisors can detect misconfiguration.
        raise SystemExit(1)

    log_startup_settings()

    if settings.INSTANCE_LOCK_ENABLED:
        instance_lock = InstanceLock(settings.INSTANCE_LOCK_PATH)
        if not instance_lock.acquire():
            logger.error("Another instance is running. Exiting.")
            # Avoid running multiple instances against the same SQLite DB.
            raise SystemExit(1)

    app = (
        Application.builder()
        .token(settings.BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    register_handlers(app, db)
    app.add_error_handler(on_error)

    logger.info("Bot starting...")
    try:
        # 可选丢弃积压更新，避免长时间宕机后消息洪峰。
        app.run_polling(drop_pending_updates=settings.DROP_PENDING_UPDATES)
    finally:
        if instance_lock:
            instance_lock.release()
            instance_lock = None


if __name__ == "__main__":
    main()
