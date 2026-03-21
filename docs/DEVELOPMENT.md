# 开发者指南

## 开发环境设置

### 1. 克隆项目

```bash
git clone <repository-url>
cd 智能提醒机器人
```

### 2. 创建虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

开发/测试依赖：

```bash
pip install -r requirements-dev.txt

# 使用锁定版本（可选）
pip install -r requirements-dev.lock
```

### 4. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入 BOT_TOKEN
```

## 测试

### 运行测试

```bash
# 全部测试
pytest tests/ -v

# 带覆盖率
pytest tests/ --cov=src --cov-report=term

# 单个模块
pytest tests/test_bot.py -v
```

### 测试覆盖率要求

- 总体覆盖率目标 ≥ 80%
- CI 强制门槛：`--cov-fail-under=70`
- CI 会执行 `ruff check .` 与 `preflight.py` 烟囱检查

## 代码规范

### 目录结构

```
src/
├── bot/        # Telegram 处理器
├── database/   # 数据库操作
├── models/     # 数据模型
└── services/   # 业务逻辑
```

### 命名规范

- 类名：PascalCase
- 函数/变量：snake_case
- 常量：UPPER_CASE

### 格式化与检查

```bash
black .
ruff check .
```

建议在提交前执行：

```bash
pytest tests/ -v --cov=src --cov-report=term
```

生产相关脚本建议也纳入回归：

```bash
pytest tests/test_preflight.py tests/test_backup_db.py tests/test_restore_db.py -v
```

## 扩展开发

### 添加新命令

```python
# src/bot/commands.py
async def my_command(self, update, context):
    await update.message.reply_text("Hello")
```

```python
# src/bot/handlers.py
app.add_handler(TGCommandHandler("mycommand", cmd.my_command))
```

### 实现 AI 解析器

```python
# src/services/ai_parser.py
class OpenAIParser(AIParser):
    def parse(self, text: str) -> Optional[ParseResult]:
        # 实现 OpenAI API 调用
        pass
```

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| BOT_TOKEN | 是 | Telegram Bot Token |
| DATABASE_PATH | 否 | 数据库路径 |
| DATABASE_URL | 否 | 兼容旧配置（sqlite URL） |
| TIMEZONE | 否 | 时区，默认 Asia/Shanghai |
| AI_API_KEY | 否 | SiliconFlow API 密钥 |
| AI_MODEL | 否 | SiliconFlow 模型名称 |
| AI_BASE_URL | 否 | SiliconFlow API 地址 |
| AI_PROVIDER | 否 | 解析器选择（siliconflow/openai/claude/rule） |
| OPENAI_API_KEY | 否 | OpenAI API 密钥 |
| OPENAI_MODEL | 否 | OpenAI 模型名称 |
| OPENAI_BASE_URL | 否 | OpenAI API 地址 |
| ANTHROPIC_API_KEY | 否 | Claude API 密钥 |
| ANTHROPIC_MODEL | 否 | Claude 模型名称 |
| ANTHROPIC_BASE_URL | 否 | Claude API 地址 |
| LOG_LEVEL | 否 | 日志等级（默认 INFO） |
| SCHEDULER_INTERVAL_SECONDS | 否 | 调度扫描间隔（秒） |
| SCHEDULER_BATCH_SIZE | 否 | 单次调度批量领取条数 |
| SCHEDULER_LOCK_SECONDS | 否 | 调度锁定时长（秒） |
| SCHEDULER_SEND_CONCURRENCY | 否 | 并发发送上限 |
| SCHEDULER_SEND_TIMEOUT_SECONDS | 否 | 单次发送超时保护（秒） |
| DROP_PENDING_UPDATES | 否 | 是否丢弃积压更新（避免宕机后消息洪峰） |
| DB_QUICK_CHECK_ON_STARTUP | 否 | 启动时是否执行 SQLite `PRAGMA quick_check`（默认 true） |
| HEALTHCHECK_ENABLED | 否 | 是否启用健康检查（默认 true） |
| HEALTHCHECK_HOST | 否 | 健康检查监听地址 |
| HEALTHCHECK_PORT | 否 | 健康检查端口 |
| HEALTHCHECK_PATH | 否 | 健康检查路径 |
| HEALTHCHECK_CHECK_TIMEOUT_SECONDS | 否 | 健康检查内部 DB ping 超时秒数（默认 3） |
| INSTANCE_LOCK_ENABLED | 否 | 是否启用实例锁（默认开启） |
| INSTANCE_LOCK_PATH | 否 | 实例锁文件路径 |

约束说明：

- `LOG_LEVEL` 必须为 `CRITICAL/ERROR/WARNING/INFO/DEBUG/NOTSET`
- `SCHEDULER_SEND_CONCURRENCY` 范围为 `1-50`
- `SCHEDULER_SEND_TIMEOUT_SECONDS` 范围为 `(0, 300]`
- `SCHEDULER_LOCK_SECONDS` 必须 `>= SCHEDULER_SEND_TIMEOUT_SECONDS`
- `HEALTHCHECK_PATH` 必须以 `/` 开头且不能包含空格
- `HEALTHCHECK_CHECK_TIMEOUT_SECONDS` 范围为 `(0, 30]`
- `DATABASE_PATH` 不能为空字符串

## 常见问题

### Q: 如何获取 Bot Token？

1. 在 Telegram 中找到 @BotFather
2. 发送 `/newbot`
3. 按提示设置名称
4. 获取 Token

### Q: 测试失败怎么办？

```bash
# 清理缓存
rm -rf __pycache__ .pytest_cache
pytest tests/ -v
```

### Q: 如何验证上线前检查逻辑？

```bash
python scripts/preflight.py --help
python scripts/preflight.py --strict-warnings
```

### Q: 如何本地演练恢复流程？

```bash
python scripts/backup_db.py --db ./reminders.db --out-dir ./backups --keep 3
python scripts/restore_db.py --db ./reminders.db --from ./backups/reminders_xxx.db --snapshot-dir ./backups/pre-restore
```
