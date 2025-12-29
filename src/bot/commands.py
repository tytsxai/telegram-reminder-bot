"""命令处理模块"""
from telegram import Update
from telegram.ext import ContextTypes
from src.database.db import Database
from src.services.reminder import ReminderService
from src.services.ai_parser import RuleBasedParser


class CommandHandler:
    """命令处理器"""
    
    def __init__(self, db: Database):
        self.db = db
        self.reminder_service = ReminderService(db)
        self.parser = RuleBasedParser()
    
    async def start(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """处理 /start 命令"""
        await update.message.reply_text(
            "👋 欢迎使用智能提醒机器人！\n\n"
            "命令列表：\n"
            "/remind <内容> - 设置提醒\n"
            "/list - 查看提醒列表\n"
            "/delete <ID> - 删除提醒\n"
            "/help - 获取帮助"
        )
    
    async def help(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """处理 /help 命令"""
        await update.message.reply_text(
            "📖 使用帮助\n\n"
            "自然语言示例：\n"
            "• 明天上午9点提醒我开会\n"
            "• 每天8点提醒我喝水\n"
            "• 后天下午3点提醒我买菜"
        )
    
    async def remind(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """处理 /remind 命令"""
        if not context.args:
            await update.message.reply_text("请输入提醒内容")
            return
        
        text = " ".join(context.args)
        result = self.parser.parse(text)
        
        if result is None:
            await update.message.reply_text(
                "无法解析时间，请使用格式：\n"
                "明天9点提醒我开会"
            )
            return
        
        reminder = await self.reminder_service.create_reminder(
            user_id=update.effective_user.id,
            chat_id=update.effective_chat.id,
            content=result.content,
            remind_at=result.remind_at,
            repeat_type=result.repeat_type
        )
        
        await update.message.reply_text(
            f"✅ 提醒已创建！\n"
            f"内容: {reminder.content}\n"
            f"时间: {reminder.remind_at.strftime('%Y-%m-%d %H:%M')}"
        )
    
    async def list_reminders(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """处理 /list 命令"""
        reminders = await self.reminder_service.get_user_reminders(
            update.effective_user.id
        )
        
        if not reminders:
            await update.message.reply_text("📭 暂无提醒")
            return
        
        lines = ["📋 提醒列表：\n"]
        for r in reminders:
            lines.append(
                f"[{r.id}] {r.content}\n"
                f"    ⏰ {r.remind_at.strftime('%m-%d %H:%M')}"
            )
        
        await update.message.reply_text("\n".join(lines))
    
    async def delete(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """处理 /delete 命令"""
        if not context.args:
            await update.message.reply_text("请输入提醒ID")
            return
        
        try:
            reminder_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("ID必须是数字")
            return
        
        result = await self.reminder_service.delete_reminder(reminder_id)
        if result:
            await update.message.reply_text("✅ 提醒已删除")
        else:
            await update.message.reply_text("❌ 提醒不存在")
    
    async def handle_message(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """处理自然语言消息"""
        text = update.message.text
        result = self.parser.parse(text)
        
        if result is None:
            await update.message.reply_text(
                "💡 试试这样说：\n"
                "明天9点提醒我开会"
            )
            return
        
        reminder = await self.reminder_service.create_reminder(
            user_id=update.effective_user.id,
            chat_id=update.effective_chat.id,
            content=result.content,
            remind_at=result.remind_at,
            repeat_type=result.repeat_type
        )
        
        await update.message.reply_text(
            f"✅ 提醒已创建！\n"
            f"内容: {reminder.content}\n"
            f"时间: {reminder.remind_at.strftime('%Y-%m-%d %H:%M')}"
        )
