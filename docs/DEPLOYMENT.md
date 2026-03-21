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
SCHEDULER_SEND_TIMEOUT_SECONDS=30
DROP_PENDING_UPDATES=false
DB_QUICK_CHECK_ON_STARTUP=true

# 速率限制（可选，0=不限制，默认20次/分钟/用户）
AI_RATE_LIMIT_PER_MINUTE=20

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

可按实际部署显式传入关键参数（便于 CI/CD 固化检查）：

```bash
python scripts/preflight.py \
  --healthcheck-enabled true \
  --healthcheck-host 0.0.0.0 \
  --healthcheck-port 8080 \
  --db-quick-check-on-startup true \
  --instance-lock-enabled true \
  --strict-warnings
```

说明：

- `errors` 非空：阻断上线。
- `warnings` 非空：需要人工评估并记录豁免理由。
- `BOT_TOKEN` 为空或格式非法（应类似 `123456:xxxxx`）会被视为阻断项。
- `healthcheck` 启用时会额外校验 `HEALTHCHECK_HOST:HEALTHCHECK_PORT` 可绑定，避免启动时才因端口冲突失败。

如需将 warning 也作为阻断项（推荐用于 CI/CD）：

```bash
python scripts/preflight.py --strict-warnings
```

首次启动会自动初始化数据库并执行迁移。

`SCHEDULER_SEND_TIMEOUT_SECONDS` 用于限制单次消息发送阻塞时间，
建议小于等于 `SCHEDULER_LOCK_SECONDS`（配置校验会强制此约束）。

默认会执行一次 SQLite `PRAGMA quick_check(1)` 快速完整性检查；
若校验失败，进程会直接退出并由进程守护器拉起，避免带损坏数据继续运行。

默认启用实例锁，确保只运行一个实例（防止重复提醒）。

数据库初始化会尽力将 SQLite 文件权限收敛为 `600`（Windows 平台除外），
降低误读误写风险。

## 健康检查

健康检查默认开启；启用后可通过如下方式探测：

```bash
curl http://127.0.0.1:8080/healthz
```

返回示例：

```json
{
  "ok": true,
  "status": "ok",
  "db_status": "ok",
  "scheduler_status": "ok"
}
```

当 `ok=false` 时，请优先看：

- `db_status`: `ok | timeout | error`
- `scheduler_status`: `ok | not_started | not_running | claim_failed | processing_failed | lagging_or_stalled`

说明：

- `claim_failed` 通常表示数据库领取任务阶段连续失败（当前阈值 3）。
- `processing_failed` 通常表示提醒处理阶段连续失败（当前阈值 10）。

## 备份与恢复

使用脚本执行 SQLite 备份：

```bash
python scripts/backup_db.py --db /path/to/reminders.db --out-dir /var/backups/reminder --keep 7
```

默认会先执行 `quick_check(1)`；如仅做应急拷贝可临时跳过：

```bash
python scripts/backup_db.py --db /path/to/reminders.db --out-dir /var/backups/reminder --keep 7 --skip-quick-check
```

注意事项：

- `--keep` 必须为 `>= 0` 的整数（`0` 表示不执行历史清理）。
- `--out-dir` 必须是目录路径；若路径已存在但不是目录，脚本会失败退出。
- 备份文件权限默认设置为 `600`（仅当前用户可读写），避免数据泄露。

恢复流程：

1) 停止服务
2) 执行恢复脚本（会先对当前数据库做快照）
3) 启动服务

```bash
python scripts/restore_db.py \
  --db /path/to/reminders.db \
  --from /var/backups/reminder/reminders_YYYYmmdd_HHMMSS.db \
  --snapshot-dir /var/backups/reminder/pre-restore
```

恢复脚本会：

- 校验备份文件完整性（`quick_check`）
- 原子替换目标数据库
- 目标文件权限收敛为 `600`

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
User=reminder
Group=reminder
UMask=0077
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=/var/lib/reminder /var/backups/reminder
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

## 版本升级

升级前务必先执行数据备份，再替换代码/镜像。

### 本地/systemd 升级流程

```bash
# 1. 备份数据库
python scripts/backup_db.py --db /path/to/reminders.db --out-dir /var/backups/reminder --keep 7

# 2. 拉取新代码
git pull

# 3. 更新依赖
source venv/bin/activate
pip install -r requirements.txt

# 4. 执行上线前自检（失败即停止）
python scripts/preflight.py --strict-warnings

# 5. 重启服务
sudo systemctl restart reminder-bot

# 6. 验证健康状态
curl http://127.0.0.1:8080/healthz
```

### Docker 升级流程

```bash
# 1. 备份数据库（在容器内执行）
docker exec telegram-reminder-bot-app \
  python /app/scripts/backup_db.py --db /app/data/reminders.db --out-dir /app/data/backups --keep 7

# 2. 拉取新镜像并重启
IMAGE_TAG=新版本号 docker-compose pull
IMAGE_TAG=新版本号 docker-compose up -d

# 3. 验证健康状态
curl http://127.0.0.1:8080/healthz
```

若升级后健康检查持续失败，执行回滚：

```bash
# 代码/镜像回滚到上一版本
IMAGE_TAG=上一版本号 docker-compose up -d

# 数据库回滚（如有必要）
python scripts/restore_db.py \
  --db /path/to/reminders.db \
  --from /var/backups/reminder/reminders_YYYYmmdd_HHMMSS.db \
  --snapshot-dir /var/backups/reminder/pre-restore
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
`DATABASE_PATH` 时使用 `/app/data/reminders.db`，`INSTANCE_LOCK_PATH` 默认为
`/app/data/reminder-bot.lock`，避免只读根文件系统下锁文件写入失败。
如需自定义路径，可在 `.env` 中覆盖对应变量或修改 compose 文件的 volume 绑定。

compose 默认启用容器只读根文件系统（`read_only: true`）与 `tmpfs /tmp`，
数据库与备份请统一落到持久化卷（如 `/app/data`）。
compose 同时设置 `stop_grace_period: 90s`，为调度器在途任务留出优雅停机窗口。

### 数据持久化

建议将数据库文件挂载到宿主机：

```bash
-v /var/lib/reminder:/app/data
```

并在 `.env` 中设置：

```
DATABASE_PATH=/app/data/reminders.db
```
