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
│            HealthCheck Server          │
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
- **HealthCheckServer**: 监控健康检查端点

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
    DATABASE_PATH: str
    TIMEZONE: str
    AI_API_KEY: Optional[str]
    AI_BASE_URL: Optional[str]
    AI_PROVIDER: Optional[str]
    LOG_LEVEL: str
    SCHEDULER_INTERVAL_SECONDS: int
    SCHEDULER_BATCH_SIZE: int
    SCHEDULER_LOCK_SECONDS: int
    SCHEDULER_SEND_CONCURRENCY: int
    HEALTHCHECK_ENABLED: bool
    DROP_PENDING_UPDATES: bool
    INSTANCE_LOCK_ENABLED: bool
```

### 调度器流程

```
┌──────────┐   interval   ┌──────────────────────┐
│Scheduler │────────────▶│claim_pending_reminders│
└──────────┘              └──────────┬───────────┘
                                    │ (lock + batch)
                         ┌──────────▼───────────┐
                         │ send_reminder (fanout)│
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼───────────┐
                         │  process_reminder    │
                         │  (handle repeat)     │
                         └──────────────────────┘
```

调度器在发送前会写入 `send_attempt_for/send_attempt_until`，用于标记“正在发送”
并在崩溃恢复时减少重复发送。发送成功或停用后会清理该标记。

## 技术栈

| 组件 | 技术 |
|------|------|
| Bot框架 | python-telegram-bot 20.x |
| 调度器 | APScheduler |
| 数据库 | SQLite + aiosqlite |
| 配置 | pydantic-settings |
| 测试 | pytest + pytest-asyncio |

## 工具模块

### time_utils

时间处理工具，统一 UTC 与本地时区转换：

- `now_utc()` - 获取当前 UTC 时间
- `now_in_timezone()` - 获取配置时区的当前时间
- `to_utc()` / `from_utc()` - 时区转换
- `add_months()` - 月份加减（处理月末边界）

### instance_lock

文件锁实现，防止多实例同时运行：

- `InstanceLock.acquire()` - 获取锁
- `InstanceLock.release()` - 释放锁

## 数据库迁移策略

- 使用 `schema_version` 表记录数据库版本。
- 启动时按版本依次应用迁移（补字段、创建索引）。
- 新版本只追加迁移步骤，保证向后兼容。
