# 智能提醒机器人

一个基于 Telegram 的智能提醒机器人，支持自然语言设置提醒，预留 AI 接口扩展能力。

## 功能特性

- 自然语言解析：直接发送"明天9点提醒我开会"
- 重复提醒：支持每日/每周/每月重复
- 命令操作：/remind、/list（支持分页）、/delete
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
DROP_PENDING_UPDATES=false

# 监控端点（可选）
HEALTHCHECK_ENABLED=false
HEALTHCHECK_HOST=127.0.0.1
HEALTHCHECK_PORT=8080
HEALTHCHECK_PATH=/healthz

# 实例锁（默认开启，防止重复运行）
INSTANCE_LOCK_ENABLED=true
INSTANCE_LOCK_PATH=reminder-bot.lock
```

兼容旧配置（可选）：
```
DATABASE_URL=sqlite+aiosqlite:///./reminders.db
```

启用健康检查后，可通过 `http://127.0.0.1:8080/healthz` 进行探测。

### 4. 运行

```bash
source venv/bin/activate
python main.py
```

## 使用方法

### 命令列表

| 命令 | 说明 | 示例 |
|------|------|------|
| `/start` | 启动机器人 | `/start` |
| `/help` | 获取帮助 | `/help` |
| `/remind` | 设置提醒 | `/remind 明天9点提醒我开会` |
| `/list` | 查看提醒列表（可分页） | `/list 1` |
| `/delete` | 删除提醒 | `/delete 1` |

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

## License

MIT License
