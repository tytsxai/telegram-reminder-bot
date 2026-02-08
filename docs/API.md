# API 文档

## 概述

本文档描述智能提醒机器人的内部 API 接口，供开发者集成和扩展使用。

## 目录

- [数据模型](#数据模型)
- [数据库接口](#数据库接口)
- [服务层接口](#服务层接口)
- [AI 解析接口](#ai-解析接口)

---

## 数据模型

### RepeatType 枚举

```python
class RepeatType(str, Enum):
    NONE = "none"      # 不重复
    DAILY = "daily"    # 每日
    WEEKLY = "weekly"  # 每周
    MONTHLY = "monthly" # 每月
```

### Reminder 模型

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| user_id | int | Telegram 用户 ID |
| chat_id | int | Telegram 聊天 ID |
| content | str | 提醒内容 |
| remind_at | datetime | 提醒时间（UTC） |
| repeat_type | RepeatType | 重复类型 |
| repeat_weekday | int/None | 每周重复的星期（0=周一） |
| repeat_monthday | int/None | 每月重复的日期（1-31） |
| is_active | bool | 是否激活 |
| locked_until | datetime/None | 锁定截止时间（防并发） |
| last_sent_at | datetime/None | 上次发送时间 |
| last_sent_for | datetime/None | 上次发送对应的 remind_at |
| send_attempt_for | datetime/None | 当前发送尝试对应的 remind_at |
| send_attempt_until | datetime/None | 发送尝试锁定截止时间 |
| created_at | datetime | 创建时间（UTC） |

**方法：**

```python
# 转换为字典
reminder.to_dict() -> dict

# 从字典创建
Reminder.from_dict(data: dict) -> Reminder
```

---

## 数据库接口

### Database 类

```python
from src.database.db import Database

db = Database(db_path="reminders.db")
```

#### 方法

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `init_db()` | - | None | 初始化数据库表 |
| `create_reminder()` | Reminder | Reminder | 创建提醒 |
| `get_reminder()` | id: int | Reminder/None | 获取单个提醒 |
| `get_user_reminders()` | user_id: int, chat_id: int, limit?: int, offset?: int | List[Reminder] | 获取用户提醒（可分页） |
| `get_pending_reminders()` | - | List[Reminder] | 获取待发送提醒 |
| `claim_pending_reminders()` | limit: int, lock_seconds: int | List[Reminder] | 领取并锁定待发送提醒 |
| `update_reminder()` | Reminder | bool | 更新提醒 |
| `delete_reminder()` | id: int | bool | 删除提醒 |
| `delete_reminder_by_user()` | id: int, user_id: int, chat_id: int | bool | 按用户删除提醒 |
| `ping()` | - | bool | 数据库连通性检查 |
| `quick_check()` | - | bool | SQLite 快速完整性检查（`PRAGMA quick_check`） |

**示例：**

```python
async def example():
    db = Database()
    await db.init_db()
    
    # 创建提醒
    reminder = Reminder(
        user_id=123,
        chat_id=456,
        content="开会",
        remind_at=datetime.now()
    )
    created = await db.create_reminder(reminder)
    print(f"Created: {created.id}")
```

---

## 服务层接口

### ReminderService 类

```python
from src.services.reminder import ReminderService

service = ReminderService(db)
```

#### 方法

| 方法 | 说明 |
|------|------|
| `create_reminder()` | 创建提醒 |
| `get_reminder(id)` | 获取提醒 |
| `get_user_reminders(user_id, chat_id, limit=None, offset=None)` | 获取用户提醒（可分页） |
| `delete_reminder(id)` | 删除提醒 |
| `delete_reminder_by_user(id, user_id, chat_id)` | 按用户删除提醒 |
| `process_reminder(reminder, sent_at, sent_for)` | 处理提醒（重复逻辑） |

### SchedulerService 类

```python
from src.services.scheduler import SchedulerService

scheduler = SchedulerService(db, send_callback, interval_seconds=30)
scheduler.start()
```

| 方法 | 说明 |
|------|------|
| `start()` | 启动调度器 |
| `stop()` | 停止调度器 |

**配置参数（通过环境变量）：**

| 参数 | 说明 |
|------|------|
| `interval_seconds` | 扫描间隔（秒），默认 30 |
| `batch_size` | 单次批量领取条数，默认 200 |
| `lock_seconds` | 锁定时长（秒），默认 120 |
| `send_concurrency` | 并发发送上限，默认 5 |

### HealthCheckServer 类

```python
from src.services.healthcheck import HealthCheckServer

server = HealthCheckServer(host="127.0.0.1", port=8080, path="/healthz")
await server.start()
```

| 方法 | 说明 |
|------|------|
| `start()` | 启动健康检查 HTTP 服务 |
| `stop()` | 停止健康检查服务 |

---

## AI 解析接口

### ParseResult 数据类

```python
@dataclass
class ParseResult:
    content: str        # 提醒内容
    remind_at: datetime # 提醒时间
    repeat_type: RepeatType = RepeatType.NONE
    repeat_weekday: Optional[int] = None
    repeat_monthday: Optional[int] = None
```

### AIParser 抽象基类

```python
class AIParser(ABC):
    @abstractmethod
    def parse(self, text: str) -> Optional[ParseResult]:
        pass
```

### 内置实现

| 类 | 说明 |
|------|------|
| `RuleBasedParser` | 基于正则的规则解析器 |
| `SiliconFlowParser` | SiliconFlow/DeepSeek 解析器 |
| `OpenAIParser` | OpenAI 解析器 |
| `ClaudeParser` | Claude 解析器 |

### 默认解析器选择

```python
from src.services.ai_parser import get_default_parser

parser = get_default_parser()
```

### 扩展 AI 解析器

```python
from src.services.ai_parser import AIParser, ParseResult

class MyAIParser(AIParser):
    def parse(self, text: str) -> Optional[ParseResult]:
        # 调用你的 AI API
        response = call_ai_api(text)
        return ParseResult(
            content=response.content,
            remind_at=response.time,
            repeat_type=response.repeat
        )
```
