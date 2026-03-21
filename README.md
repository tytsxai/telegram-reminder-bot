# 智能提醒机器人

一个基于 Telegram 的智能提醒机器人，支持自然语言设置提醒，预留 AI 接口扩展能力。

## 功能特性

- 自然语言解析：直接发送"明天9点提醒我开会"
- 重复提醒：支持每日/每周/每月重复
- 命令操作：/remind、/list（支持分页）、/delete、/cancel
- AI 接口预留：可扩展 OpenAI/Claude 解析能力
- 定时调度：自动发送到期提醒

## 快速开始

### 1. 环境要求

- Python 3.11+
- Telegram Bot Token（从 @BotFather 获取）

### 2. 安装

```bash
# 克隆项目
git clone <repository-url>
cd 智能提醒机器人

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

生产环境建议使用锁定依赖：

```bash
pip install -r requirements.lock
```

### 3. 配置

创建 `.env` 文件：

```bash
BOT_TOKEN=your_telegram_bot_token
TIMEZONE=Asia/Shanghai
DATABASE_PATH=reminders.db

# AI 配置（可选，SiliconFlow/DeepSeek）
AI_PROVIDER=siliconflow
AI_API_KEY=your_api_key
AI_MODEL=deepseek-ai/DeepSeek-V3
AI_BASE_URL=

# OpenAI（可选）
OPENAI_API_KEY=
OPENAI_MODEL=
OPENAI_BASE_URL=

# Claude（可选）
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=
ANTHROPIC_BASE_URL=

# 运行配置（可选）
LOG_LEVEL=INFO
SCHEDULER_INTERVAL_SECONDS=30
SCHEDULER_BATCH_SIZE=200
SCHEDULER_LOCK_SECONDS=120
SCHEDULER_SEND_CONCURRENCY=5
SCHEDULER_SEND_TIMEOUT_SECONDS=30
DROP_PENDING_UPDATES=false
DB_QUICK_CHECK_ON_STARTUP=true

# 速率限制（可选，0=不限制，默认20次/分钟/用户）
AI_RATE_LIMIT_PER_MINUTE=20

# 监控端点（可选）
HEALTHCHECK_ENABLED=true
HEALTHCHECK_HOST=127.0.0.1
HEALTHCHECK_PORT=8080
HEALTHCHECK_PATH=/healthz
HEALTHCHECK_CHECK_TIMEOUT_SECONDS=3

# 实例锁（默认开启，防止重复运行）
INSTANCE_LOCK_ENABLED=true
# Docker 只读根文件系统时建议改为 /app/data/reminder-bot.lock
INSTANCE_LOCK_PATH=reminder-bot.lock
```

兼容旧配置（可选）：
```
DATABASE_URL=sqlite+aiosqlite:///./reminders.db
```

默认启用健康检查（`HEALTHCHECK_ENABLED=true`），可通过
`http://127.0.0.1:8080/healthz` 进行探测。

### 4. 运行

```bash
source venv/bin/activate
python scripts/preflight.py
python main.py
```

## 生产就绪最小基线（建议强制）

在生产环境，建议至少满足以下基线：

- `HEALTHCHECK_ENABLED=true`（避免“进程活着但业务挂掉”）
- `INSTANCE_LOCK_ENABLED=true`（防止多实例重复发送）
- `DB_QUICK_CHECK_ON_STARTUP=true`（启动即拦截损坏数据库）
- `SCHEDULER_SEND_TIMEOUT_SECONDS <= SCHEDULER_LOCK_SECONDS`

推荐发布门禁命令：

```bash
python scripts/preflight.py \
  --healthcheck-enabled true \
  --healthcheck-host 127.0.0.1 \
  --healthcheck-port 8080 \
  --db-quick-check-on-startup true \
  --instance-lock-enabled true \
  --strict-warnings
```

健康检查 `ok=false` 时，重点查看：

- `db_status`: `ok | timeout | error`
- `scheduler_status`: `ok | claim_failed | processing_failed | lagging_or_stalled | not_running | not_started`

## 使用方法

### 命令列表

| 命令 | 说明 | 示例 |
|------|------|------|
| `/start` | 启动机器人 | `/start` |
| `/help` | 获取帮助 | `/help` |
| `/remind` | 设置提醒 | `/remind 明天9点提醒我开会` |
| `/list` | 查看提醒列表（可分页） | `/list 1` |
| `/delete` | 删除提醒（支持交互输入 ID） | `/delete 1` |
| `/cancel` | 取消当前交互（如删除确认流程） | `/cancel` |

### 自然语言示例

直接发送消息（无需命令）：

```
明天上午9点提醒我开会
每天8点提醒我喝水
每周一8点提醒我开会
每月1号8点提醒我交房租
后天下午3点提醒我买菜
```

支持的时间词：
- 日期：今天、明天、后天、下周X、具体日期（YYYY-MM-DD）
- 时间：X点、X点X分、上午/下午
- 重复：每天、每周一~周日、每月1号~31号

分页示例：

```
/list 1
/list 2 50
```

## 项目结构

```
智能提醒机器人/
├── main.py              # 入口文件
├── requirements.txt     # 依赖
├── src/
│   ├── config.py        # 配置管理
│   ├── bot/             # Bot 处理器
│   ├── database/        # 数据库操作
│   ├── models/          # 数据模型
│   └── services/        # 业务服务
├── tests/               # 测试文件
└── docs/                # 文档
```

## 测试

```bash
# 运行所有测试
pip install -r requirements-dev.txt
pytest tests/ -v

# 带覆盖率
pytest tests/ -v --cov=src --cov-report=term
```

## 文档

- [API 文档](docs/API.md)
- [架构设计](docs/ARCHITECTURE.md)
- [开发指南](docs/DEVELOPMENT.md)
- [部署指南](docs/DEPLOYMENT.md)
- [故障排查](docs/TROUBLESHOOTING.md)
- [运行手册](docs/OPERATIONS.md)
- [变更记录](CHANGELOG.md)

## 上线前最小检查（建议）

```bash
python scripts/preflight.py
```

`preflight` 会输出：

- `ok=false`：存在阻断上线的问题（如配置非法、数据库不可写、实例锁不可用、健康检查端口冲突）
- `warnings`：非阻断但高风险项（如健康检查关闭、`.env` 权限过宽、`.env` 重复键覆盖）

建议将以下项目作为发布门槛：

- `ok=true`
- `warnings` 已评估并有处置记录

如果你希望在 CI/CD 中把 warning 也视为阻断项，可启用严格模式：

```bash
python scripts/preflight.py --strict-warnings
```

严格模式下只要存在 warning 就返回非 0 退出码，适合做发布门禁。

## 备份与恢复（生产）

备份（默认先做 `quick_check` 再备份）：

```bash
python scripts/backup_db.py --db /path/to/reminders.db --out-dir /var/backups/reminder --keep 7
```

恢复（先对当前线上库做快照，再原子替换）：

```bash
python scripts/restore_db.py --db /path/to/reminders.db --from /var/backups/reminder/reminders_YYYYmmdd_HHMMSS.db --snapshot-dir /var/backups/reminder/pre-restore
```

## License

MIT License
