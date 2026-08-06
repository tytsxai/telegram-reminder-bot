# 智能提醒机器人（telegram-reminder-bot）

> **Telegram reminder bot** — 自然语言设置提醒，支持每日/每周/每月重复，内置调度与可选 AI 解析扩展。

开源、自托管的 Telegram 提醒助手：直接发「明天 9 点提醒我开会」，或用 `/remind` 命令；到期自动推送。

- 仓库：https://github.com/tytsxai/telegram-reminder-bot
- 入口：`python main.py`
- License：MIT

## 项目是什么 / 解决什么问题

在 Telegram 里管理个人提醒，而无需日历 App：

- 规则 + 自然语言时间解析（今天/明天/后天、上下午、每周 X、每月 N 号等）
- 一次性与重复提醒（每日 / 每周 / 每月）
- `/list` 分页查看、`/delete` 删除、`/cancel` 取消交互
- 定时调度批量发送，可选 OpenAI / Claude / SiliconFlow 等 AI 扩展
- 生产向能力：健康检查、实例锁、preflight、备份恢复

## 适合谁

| 角色 | 场景 |
|------|------|
| 个人用户 | 会议、喝水、交租等日常提醒 |
| 自托管运维 | 长期跑一个稳定的 reminder bot |
| 开发者 | APScheduler + aiosqlite + python-telegram-bot 参考实现 |

## 核心功能

- 自然语言解析：直接发送「明天 9 点提醒我开会」
- 重复提醒：每日 / 每周 / 每月
- 命令：`/remind`、`/list`（分页）、`/delete`、`/cancel`
- AI 接口预留：可配置 SiliconFlow / OpenAI / Anthropic
- 调度：可配置轮询间隔、批量大小、并发发送、锁超时
- 监控：默认可启用 `http://127.0.0.1:8080/healthz`

## 技术栈

- Python 3.11+
- python-telegram-bot
- APScheduler
- aiosqlite + pydantic-settings
- pytz 时区

## 快速开始

### 环境要求

- Python 3.11+
- Telegram Bot Token（[@BotFather](https://t.me/BotFather)）

### 安装

```bash
git clone https://github.com/tytsxai/telegram-reminder-bot.git
cd telegram-reminder-bot

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# 生产建议：pip install -r requirements.lock
```

### 配置

```bash
cp .env.example .env
```

最小配置示例：

```bash
BOT_TOKEN=your_telegram_bot_token
TIMEZONE=Asia/Shanghai
DATABASE_PATH=reminders.db

# AI（可选）
AI_PROVIDER=siliconflow
AI_API_KEY=
AI_MODEL=deepseek-ai/DeepSeek-V3

# 运行（可选）
LOG_LEVEL=INFO
SCHEDULER_INTERVAL_SECONDS=30
HEALTHCHECK_ENABLED=true
HEALTHCHECK_HOST=127.0.0.1
HEALTHCHECK_PORT=8080
HEALTHCHECK_PATH=/healthz
INSTANCE_LOCK_ENABLED=true
INSTANCE_LOCK_PATH=reminder-bot.lock
```

兼容旧配置：`DATABASE_URL=sqlite+aiosqlite:///./reminders.db`。

完整可选变量（OpenAI / Claude、速率限制、调度并发等）见 `.env.example`。

### 运行

```bash
source venv/bin/activate
python scripts/preflight.py
python main.py
```

Docker：

```bash
docker compose up -d --build
```

## 使用方法

### 命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `/start` | 启动 | `/start` |
| `/help` | 帮助 | `/help` |
| `/remind` | 设置提醒 | `/remind 明天9点提醒我开会` |
| `/list` | 列表（可分页） | `/list 1` |
| `/delete` | 删除 | `/delete 1` |
| `/cancel` | 取消当前交互 | `/cancel` |

### 自然语言示例

无需命令也可直接发送：

```text
明天上午9点提醒我开会
每天8点提醒我喝水
每周一8点提醒我开会
每月1号8点提醒我交房租
后天下午3点提醒我买菜
```

支持的时间词包括：今天/明天/后天、下周 X、`YYYY-MM-DD`、X 点/X 点 X 分、上午/下午、每天/每周一~日/每月 1~31 号。

分页：`/list 1`、`/list 2 50`。

## 生产就绪基线

建议生产至少：

- `HEALTHCHECK_ENABLED=true`
- `INSTANCE_LOCK_ENABLED=true`（防多实例重复发送）
- `DB_QUICK_CHECK_ON_STARTUP=true`
- `SCHEDULER_SEND_TIMEOUT_SECONDS <= SCHEDULER_LOCK_SECONDS`

```bash
python scripts/preflight.py \
  --healthcheck-enabled true \
  --healthcheck-host 127.0.0.1 \
  --healthcheck-port 8080 \
  --db-quick-check-on-startup true \
  --instance-lock-enabled true \
  --strict-warnings
```

健康检查 `ok=false` 时关注：`db_status`、`scheduler_status`（如 `lagging_or_stalled` / `claim_failed` 等）。

## 项目结构

```text
telegram-reminder-bot/
├── main.py
├── requirements.txt
├── src/
│   ├── config.py
│   ├── bot/
│   ├── database/
│   ├── models/
│   └── services/
├── scripts/          # preflight / backup / restore
├── tests/
└── docs/
```

## 使用场景

- 个人待办与会议提醒
- 习惯打卡类重复提醒（喝水、锻炼）
- 月付账单提醒

## 限制与注意事项

- 依赖 Bot 进程常驻；停机期间到期提醒不会发送（重启后由调度逻辑处理待发送项，以代码为准）
- 多实例同时跑同一 Bot 会导致重复发送或冲突——务必开实例锁
- AI 解析为增强能力；核心规则解析不依赖 AI Key 也可使用常见中文时间表达
- Docker 只读根文件系统时，将 `INSTANCE_LOCK_PATH` 指到可写数据目录（如 `/app/data/...`）

## 测试

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
pytest tests/ -v --cov=src --cov-report=term
```

## 文档

- [API](docs/API.md) · [架构](docs/ARCHITECTURE.md) · [开发](docs/DEVELOPMENT.md)
- [部署](docs/DEPLOYMENT.md) · [排障](docs/TROUBLESHOOTING.md) · [运行手册](docs/OPERATIONS.md)
- [变更记录](CHANGELOG.md)

## 备份与恢复

```bash
python scripts/backup_db.py --db /path/to/reminders.db --out-dir /var/backups/reminder --keep 7
python scripts/restore_db.py --db /path/to/reminders.db \
  --from /var/backups/reminder/reminders_YYYYmmdd_HHMMSS.db \
  --snapshot-dir /var/backups/reminder/pre-restore
```

## SEO / 检索关键词

Telegram 提醒机器人, Telegram reminder bot, 自然语言提醒, 重复提醒 bot, APScheduler Telegram, 智能提醒, self-hosted reminder bot

## License

MIT License
