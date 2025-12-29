# 架构设计文档

## 系统概述

智能提醒机器人采用分层架构设计，实现关注点分离和模块化。

## 架构图

```
┌─────────────────────────────────────────┐
│           Telegram Bot API              │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│              Bot Layer                  │
│  ┌─────────────┐  ┌─────────────────┐   │
│  │  Commands   │  │    Handlers     │   │
│  └─────────────┘  └─────────────────┘   │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│           Service Layer                 │
│  ┌──────────┐ ┌─────────┐ ┌─────────┐   │
│  │ Reminder │ │Scheduler│ │AIParser │   │
│  └──────────┘ └─────────┘ └─────────┘   │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│            Data Layer                   │
│  ┌──────────┐      ┌─────────────┐      │
│  │ Database │      │   Models    │      │
│  └──────────┘      └─────────────┘      │
└─────────────────────────────────────────┘
```

## 分层说明

### 1. Bot Layer（表现层）

- **commands.py**: 处理 Telegram 命令
- **handlers.py**: 注册消息处理器

### 2. Service Layer（业务层）

- **ReminderService**: 提醒业务逻辑
- **SchedulerService**: 定时调度
- **AIParser**: 自然语言解析

### 3. Data Layer（数据层）

- **Database**: 异步数据库操作
- **Models**: 数据模型定义

## 核心组件

### 配置管理

使用 pydantic-settings 管理配置：

```python
# src/config.py
class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str
    TIMEZONE: str
    AI_API_KEY: Optional[str]
```

### 调度器流程

```
┌──────────┐    30s     ┌─────────────┐
│Scheduler │──────────▶│check_pending│
└──────────┘            └──────┬──────┘
                               │
                    ┌──────────▼──────────┐
                    │  get_pending_reminders│
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   send_reminder     │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  process_reminder   │
                    │  (handle repeat)    │
                    └─────────────────────┘
```

## 技术栈

| 组件 | 技术 |
|------|------|
| Bot框架 | python-telegram-bot 20.x |
| 调度器 | APScheduler |
| 数据库 | SQLite + aiosqlite |
| 配置 | pydantic-settings |
| 测试 | pytest + pytest-asyncio |
