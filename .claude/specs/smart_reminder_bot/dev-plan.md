# 智能提醒机器人 - 开发计划

## 项目概述
开发一个 Telegram 智能提醒机器人，支持自然语言设置提醒、重复提醒、任务管理，并预留 AI 接口。

## 技术栈
- Python 3.11+
- python-telegram-bot 20.x
- APScheduler 3.x
- SQLite + aiosqlite
- pytest + pytest-asyncio

## 任务分解

### T1: 项目基础架构
- **类型**: default
- **后端**: codex
- **文件范围**: `src/config.py`, `main.py`, `requirements.txt`
- **依赖**: 无
- **测试命令**: `pytest tests/test_config.py -v --cov=src/config --cov-report=term`

### T2: 数据库与模型层
- **类型**: default
- **后端**: codex
- **文件范围**: `src/models/`, `src/database/`
- **依赖**: 无
- **测试命令**: `pytest tests/test_models.py tests/test_database.py -v --cov=src/models --cov=src/database --cov-report=term`

### T3: 提醒服务与调度器
- **类型**: default
- **后端**: codex
- **文件范围**: `src/services/reminder.py`, `src/services/scheduler.py`
- **依赖**: T2
- **测试命令**: `pytest tests/test_services.py -v --cov=src/services --cov-report=term`

### T4: AI解析接口预留
- **类型**: default
- **后端**: codex
- **文件范围**: `src/services/ai_parser.py`
- **依赖**: 无
- **测试命令**: `pytest tests/test_ai_parser.py -v --cov=src/services/ai_parser --cov-report=term`

### T5: Bot处理器与命令
- **类型**: default
- **后端**: codex
- **文件范围**: `src/bot/handlers.py`, `src/bot/commands.py`
- **依赖**: T1, T2, T3, T4
- **测试命令**: `pytest tests/test_bot.py -v --cov=src/bot --cov-report=term`
