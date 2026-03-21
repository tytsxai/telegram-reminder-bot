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

`docker-compose.yml` 已设置 `stop_grace_period: 90s`，用于给调度器在途任务留出优雅停机时间。

## 运行检查清单

- `.env` 已配置并可读取
- `BOT_TOKEN` 正确
- `DATABASE_PATH` 指向可写路径
- 数据库文件权限为 `600`（启动后会自动收敛，仍建议人工核验）
- 启动日志出现 `Database quick check passed`
- Docker 部署已挂载持久化卷（/app/data）
- 仅单实例运行（默认启用实例锁）
- 已确认是否需要丢弃积压更新（`DROP_PENDING_UPDATES`）
- 健康检查开启（生产建议必开）

上线前建议执行：

```bash
python scripts/preflight.py \
  --healthcheck-enabled true \
  --healthcheck-host 127.0.0.1 \
  --healthcheck-port 8080 \
  --db-quick-check-on-startup true \
  --instance-lock-enabled true
```

返回 `{"ok": true}` 才继续发布。

建议在 CI/CD 使用严格模式：

```bash
python scripts/preflight.py --strict-warnings
```

补充要求：

- 若 `warnings` 非空，必须在发布记录中写明评估结果。
- 建议将 `preflight` 输出存档到发布工单（便于审计与回溯）。
- 若启用健康检查，`preflight` 会校验 `HEALTHCHECK_HOST:HEALTHCHECK_PORT` 可绑定，端口冲突会直接阻断发布。
- 若 `.env` 存在重复键（例如同一键配置多次），`preflight` 会发出 warning，需先清理避免“最后一条覆盖前值”的隐性配置偏差。

## 备份

使用内置脚本：

```bash
python scripts/backup_db.py --db /path/to/reminders.db --out-dir /var/backups/reminder --keep 7
```

默认会先执行 `quick_check`。如数据库已损坏且需先做取证备份，可临时加：

```bash
python scripts/backup_db.py --db /path/to/reminders.db --out-dir /var/backups/reminder --keep 7 --skip-quick-check
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
2) 使用恢复脚本执行原子替换（自动保留恢复前快照）
3) 启动服务

示例：

```bash
python scripts/restore_db.py \
  --db /path/to/reminders.db \
  --from /var/backups/reminder/reminders_20250101_020000.db \
  --snapshot-dir /var/backups/reminder/pre-restore
```

恢复后校验：

```bash
python scripts/preflight.py --bot-token "$BOT_TOKEN" --db-path /path/to/reminders.db
```

## 回滚

- 代码回滚：使用 git tag 或发布包回滚
- 数据回滚：优先使用 `restore_db.py` 指定回滚备份

## 发布检查与回滚清单（建议执行）

发布前：

1. 执行 `python scripts/preflight.py` 并归档输出
2. 确认最近备份在预期时间窗口内可用
3. 记录本次发布版本（镜像 tag / git commit）

发布后（5-10 分钟内）：

1. 检查健康端点 `ok=true`
2. 检查日志无持续 `ERROR`
3. 人工验证至少 1 条提醒可创建并按时触发

回滚触发条件（示例）：

- 连续 5 分钟健康检查失败
- 提醒发送成功率明显下降且无法快速恢复
- 启动后持续出现数据库完整性/锁异常

## 健康检查

启用后可通过：

```bash
curl http://127.0.0.1:8080/healthz
```

返回 `ok=false` 时应触发告警。

实现细节（用于防止探针连接异常拖垮服务）：

- 健康检查请求读取有超时保护，超时会返回 `408 request_timeout`。
- 单请求头数量有限制（默认最多 100 行），超过会返回 `400 too_many_headers`。
- 健康检查内部 DB ping 有独立超时（`HEALTHCHECK_CHECK_TIMEOUT_SECONDS`），超时后返回 `db_error`。

健康检查响应会包含以下关键字段：

- `db_status`: `ok | timeout | error`
- `scheduler_status`: `ok | not_started | not_running | claim_failed | processing_failed | lagging_or_stalled`
- `scheduler`: 调度器快照（含 `consecutive_claim_failures`、`consecutive_process_failures`、`last_success_at`）

当调度器卡住、停止、连续领取失败（阈值 3）或连续处理失败（阈值 10）时会返回 `scheduler_unhealthy`。

## 关键告警与处置

- `status=db_error`：优先检查数据库文件权限、磁盘空间、I/O 错误；必要时从最近备份恢复。
- `status=scheduler_unhealthy`：先重启进程；若 `scheduler_status=claim_failed`，优先排查数据库可用性与锁冲突。
- `scheduler_status=processing_failed`：说明提醒处理连续失败，优先检查 Telegram 网络、发送超时与下游 API 可用性。
- `scheduler_status=lagging_or_stalled`：检查事件循环是否被阻塞、外部 API 是否持续超时。
- 启动失败且日志包含 `database quick check failed`：停止自动重启，执行 SQLite 完整检查并走恢复流程。

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
| SCHEDULER_SEND_TIMEOUT_SECONDS | 30 | 单次发送超时保护，建议 15-60 |

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
