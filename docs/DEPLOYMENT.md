# 部署指南

## 运行环境

- Python 3.11+
- 建议使用虚拟环境（venv/uv/conda）

## 安装与初始化

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

建议生产环境使用锁定依赖：

```bash
pip install -r requirements.lock
```

## 环境变量

建议将密钥写入 `.env` 或系统环境变量：

```bash
BOT_TOKEN=your_telegram_bot_token
TIMEZONE=Asia/Shanghai
DATABASE_PATH=/var/lib/reminder/reminders.db

# AI（可选）
AI_PROVIDER=siliconflow
AI_API_KEY=your_api_key
AI_MODEL=deepseek-ai/DeepSeek-V3.2

# 监控与运行（可选）
LOG_LEVEL=INFO
SCHEDULER_INTERVAL_SECONDS=30
SCHEDULER_BATCH_SIZE=200
SCHEDULER_LOCK_SECONDS=120
SCHEDULER_SEND_CONCURRENCY=5
DROP_PENDING_UPDATES=false
DB_QUICK_CHECK_ON_STARTUP=true
HEALTHCHECK_ENABLED=true
HEALTHCHECK_HOST=0.0.0.0
HEALTHCHECK_PORT=8080
HEALTHCHECK_PATH=/healthz
HEALTHCHECK_CHECK_TIMEOUT_SECONDS=3
```

> 建议使用系统的密钥管理方案（如 systemd drop-in、容器 secret、环境变量注入）。

## 启动

```bash
source venv/bin/activate
python main.py
```

建议先执行上线前自检（失败即停止发布）：

```bash
python scripts/preflight.py
```

首次启动会自动初始化数据库并执行迁移。

默认会执行一次 SQLite `PRAGMA quick_check(1)` 快速完整性检查；
若校验失败，进程会直接退出并由进程守护器拉起，避免带损坏数据继续运行。

默认启用实例锁，确保只运行一个实例（防止重复提醒）。

## 健康检查

启用后可通过如下方式探测：

```bash
curl http://127.0.0.1:8080/healthz
```

返回示例：

```json
{"ok": true, "status": "ok"}
```

## 备份与恢复

使用脚本执行 SQLite 备份：

```bash
python scripts/backup_db.py --db /path/to/reminders.db --out-dir /var/backups/reminder --keep 7
```

注意事项：

- `--keep` 必须为 `>= 0` 的整数（`0` 表示不执行历史清理）。
- `--out-dir` 必须是目录路径；若路径已存在但不是目录，脚本会失败退出。
- 备份文件权限默认设置为 `600`（仅当前用户可读写），避免数据泄露。

恢复流程：

1) 停止服务  
2) 用最近备份替换数据库文件  
3) 启动服务  

## systemd 示例

`/etc/systemd/system/reminder-bot.service`:

```ini
[Unit]
Description=Telegram Reminder Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/reminder-bot
EnvironmentFile=/opt/reminder-bot/.env
ExecStartPre=/opt/reminder-bot/venv/bin/python /opt/reminder-bot/scripts/preflight.py
ExecStart=/opt/reminder-bot/venv/bin/python /opt/reminder-bot/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用：

```bash
sudo systemctl daemon-reload
sudo systemctl enable reminder-bot
sudo systemctl start reminder-bot
```

## 数据库迁移策略

- 启动时自动检查 `schema_version` 表。
- 逐版本执行迁移（补字段、建索引）。
- 新版本只追加迁移步骤，确保旧数据兼容。

## 生产建议

- 使用非 root 用户运行服务。
- 配置日志采集与保留策略。
- 配置外部监控，定期探测健康检查端点。
- 配置进程重启策略（systemd `Restart=always` / 容器 `restart: unless-stopped`）。
- 明确回滚入口：保留最近可用镜像与最近一次可恢复数据库备份。
- 参考 `docs/OPERATIONS.md` 的运行手册。

## Docker 部署

### 构建镜像

```bash
docker build -t telegram-reminder-bot-app:latest .
```

### 运行容器

```bash
docker run -d \
  --name telegram-reminder-bot \
  --env-file .env \
  -v /path/to/data:/app/data \
  telegram-reminder-bot-app:latest
```

### 使用 docker-compose

1. 设置 `IMAGE_TAG` 环境变量或在 `.env` 中配置（未配置默认 `latest`）
2. 启动服务：

```bash
IMAGE_TAG=latest docker-compose up -d
```

docker-compose 默认挂载 `telegram-reminder-bot-data` 到 `/app/data`，并在未设置
`DATABASE_PATH` 时使用 `/app/data/reminders.db`。如需自定义路径，可在 `.env` 中覆盖
`DATABASE_PATH` 或修改 compose 文件的 volume 绑定。

### 数据持久化

建议将数据库文件挂载到宿主机：

```bash
-v /var/lib/reminder:/app/data
```

并在 `.env` 中设置：

```
DATABASE_PATH=/app/data/reminders.db
```
