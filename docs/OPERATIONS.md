# 生产运行手册

## 启动/停止

### 直接运行

```bash
source venv/bin/activate
python main.py
```

### systemd

参见 `docs/DEPLOYMENT.md` 中的 systemd 示例。

### Docker

```bash
# 启动
docker-compose up -d

# 停止
docker-compose down

# 查看日志
docker-compose logs -f
```

## 运行检查清单

- `.env` 已配置并可读取
- `BOT_TOKEN` 正确
- `DATABASE_PATH` 指向可写路径
- Docker 部署已挂载持久化卷（/app/data）
- 仅单实例运行（默认启用实例锁）
- 已确认是否需要丢弃积压更新（`DROP_PENDING_UPDATES`）
- 健康检查开启（可选）

## 备份

使用内置脚本：

```bash
python scripts/backup_db.py --db /path/to/reminders.db --out-dir /var/backups/reminder --keep 7
```

Docker 部署可在容器内执行：

```bash
docker exec telegram-reminder-bot-app \
  python /app/scripts/backup_db.py --db /app/data/reminders.db --out-dir /app/data/backups --keep 7
```

建议通过 cron 或 systemd timer 定时执行。

### cron 配置示例

本地部署（每天凌晨 2 点备份）：

```bash
# /etc/cron.d/reminder-bot-backup
0 2 * * * root /path/to/venv/bin/python /path/to/scripts/backup_db.py --db /path/to/reminders.db --out-dir /var/backups/reminder --keep 7
```

Docker 部署：

```bash
# /etc/cron.d/reminder-bot-backup
0 2 * * * root docker exec telegram-reminder-bot-app python /app/scripts/backup_db.py --db /app/data/reminders.db --out-dir /app/data/backups --keep 7
```

### systemd timer 配置示例

创建 `/etc/systemd/system/reminder-bot-backup.service`：

```ini
[Unit]
Description=Reminder Bot Database Backup

[Service]
Type=oneshot
ExecStart=/path/to/venv/bin/python /path/to/scripts/backup_db.py --db /path/to/reminders.db --out-dir /var/backups/reminder --keep 7
```

创建 `/etc/systemd/system/reminder-bot-backup.timer`：

```ini
[Unit]
Description=Daily backup for Reminder Bot

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

启用定时器：

```bash
systemctl daemon-reload
systemctl enable --now reminder-bot-backup.timer
```

## 恢复

1) 停止服务
2) 用最近备份替换数据库文件
3) 启动服务

示例：

```bash
cp /var/backups/reminder/reminders_20250101_020000.db /path/to/reminders.db
```

## 回滚

- 代码回滚：使用 git tag 或发布包回滚
- 数据回滚：用备份文件替换数据库

## 健康检查

启用后可通过：

```bash
curl http://127.0.0.1:8080/healthz
```

返回 `ok=false` 时应触发告警。

实现细节（用于防止探针连接异常拖垮服务）：

- 健康检查请求读取有超时保护，超时会返回 `408 request_timeout`。
- 单请求头数量有限制（默认最多 100 行），超过会返回 `400 too_many_headers`。

健康检查响应会包含调度器状态与延迟信息（`scheduler_ok`/`scheduler`），
当调度器卡住或停止时会返回 `scheduler_unhealthy`。

## 日志管理

### 日志级别

通过 `LOG_LEVEL` 环境变量控制：

| 级别 | 说明 |
|------|------|
| DEBUG | 详细调试信息 |
| INFO | 常规运行信息（默认） |
| WARNING | 警告信息 |
| ERROR | 错误信息 |

### 日志轮转（logrotate）

`/etc/logrotate.d/reminder-bot`:

```
/var/log/reminder-bot/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

### systemd 日志查看

```bash
journalctl -u reminder-bot -f
journalctl -u reminder-bot --since "1 hour ago"
```

## 监控告警

### 探针/可用性监控

健康检查端点返回 JSON（非 Prometheus 指标），建议用于探针或黑盒监控。

```yaml
# blackbox.yml / 或你使用的可用性监控配置
targets:
  - http://127.0.0.1:8080/healthz
```

### 告警规则示例

```yaml
groups:
  - name: reminder-bot
    rules:
      - alert: ReminderBotDown
        expr: probe_success{job="reminder-bot"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "提醒机器人服务不可用"
```

## 性能调优

### 调度器参数

| 参数 | 默认值 | 建议 |
|------|--------|------|
| SCHEDULER_INTERVAL_SECONDS | 30 | 提醒量大时可降至 10-15 |
| SCHEDULER_BATCH_SIZE | 200 | 根据内存调整，建议 100-500 |
| SCHEDULER_LOCK_SECONDS | 120 | 应大于单批处理时间 |
| SCHEDULER_SEND_CONCURRENCY | 5 | 避免触发 Telegram 限流 |

### SQLite 优化

数据库默认启用 WAL 模式，适合读多写少场景。大量写入时可考虑：

```bash
# 定期执行 VACUUM
sqlite3 reminders.db "VACUUM;"
```

## 容量规划

| 提醒数量 | 内存占用 | 磁盘空间 |
|----------|----------|----------|
| < 10,000 | ~50 MB | ~10 MB |
| 10,000-100,000 | ~100 MB | ~100 MB |
| > 100,000 | ~200 MB+ | 建议迁移外部数据库 |
