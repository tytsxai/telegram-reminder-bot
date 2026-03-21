# 故障排查指南

## 启动失败 / 机器人无响应

- 检查 `BOT_TOKEN` 是否配置正确（格式应类似 `123456:xxxxx`）。
- 确认网络能够访问 Telegram。
- 查看日志是否包含 `BOT_TOKEN not configured` 或 `BOT_TOKEN format is invalid`。
- 若启用了健康检查，确认 `HEALTHCHECK_HOST:HEALTHCHECK_PORT` 未被占用（`preflight` 会直接报错 `Healthcheck bind failed`）。
- 若 `preflight` 警告 `.env contains duplicate keys`，请去重 `.env` 中重复键，避免配置被后续行覆盖。

建议先执行：

```bash
python scripts/preflight.py --strict-warnings
```

若返回 `ok=false`，优先修复 `errors` 中列出项。

## 实例锁导致无法启动

- 日志出现 `Another instance is running` 表示已有实例在运行。
- 确认只启动了一个进程，或关闭旧进程后重启。

## 健康检查 503

- 代表依赖不可用（数据库或调度器异常）。
- 检查数据库路径是否可写，磁盘空间是否充足。
- 若返回 `scheduler_unhealthy`，重点看 `scheduler_status`：
  - `claim_failed`：优先排查数据库连接、锁冲突、磁盘 I/O。
  - `processing_failed`：连续处理失败，优先排查 Telegram 网络连通性与发送超时配置。
  - `lagging_or_stalled`：排查事件循环阻塞与外部 API 超时。
- 查看日志中的 `db_error` / `scheduler_unhealthy` 相关信息。
- 若日志包含 `Healthcheck db ping timeout`，适当上调 `HEALTHCHECK_CHECK_TIMEOUT_SECONDS`（建议 3-10 秒）。

## 时区报错

- `Invalid TIMEZONE` 表示时区名称不合法。
- 使用标准 IANA 时区名称，例如 `Asia/Shanghai`、`UTC`。

## 数据库锁定 / 无法写入

- 确认数据库文件权限可写。
- 避免多个实例同时写同一个 SQLite 文件。
- 若需多实例部署，建议迁移到外部数据库。

## 启动时报 database quick check failed

- 含义：启动阶段执行 `PRAGMA quick_check(1)` 失败，数据库可能损坏或不可读。
- 先停止自动拉起，避免反复重启刷屏。
- 执行：`sqlite3 /path/to/reminders.db "PRAGMA integrity_check;"`。
- 若结果非 `ok`，使用最近备份恢复，再重启服务。

推荐恢复命令：

```bash
python scripts/restore_db.py \
  --db /path/to/reminders.db \
  --from /var/backups/reminder/reminders_YYYYmmdd_HHMMSS.db \
  --snapshot-dir /var/backups/reminder/pre-restore
```

## AI 解析失败

- 未配置 API Key 或 Model 时会自动回退到规则解析。
- 查看日志中 `AI parser not configured` 或请求失败日志。
- 确认 `AI_PROVIDER` 与密钥对应。

## 提醒不触发

- 检查 `SCHEDULER_INTERVAL_SECONDS` 是否过大。
- 查看日志中是否有调度器启动记录。
- 确认系统时间/时区配置正确。

## Telegram 限流 (RetryAfter)

- 日志出现 `Rate limited` 表示触发 Telegram API 限流。
- 调度器会自动延迟重试，无需手动干预。
- 可降低 `SCHEDULER_SEND_CONCURRENCY` 减少并发。

## 用户屏蔽机器人 (Forbidden)

- 日志出现 `Chat forbidden` 表示用户已屏蔽机器人。
- 对应提醒会自动标记为 `is_active=false`。
- 用户重新启用后需重新创建提醒。

## Docker 容器无法启动

- 检查 `.env` 文件是否存在且格式正确。
- 确认镜像已构建且 `IMAGE_TAG` 与镜像标签一致（未配置时默认使用 `latest`）。
- 查看容器日志：`docker-compose logs`。
- 确认 `INSTANCE_LOCK_PATH` 指向可写卷（默认 `/app/data/reminder-bot.lock`）。

## 数据库迁移失败

- 日志出现 `schema_version` 相关错误时，检查数据库文件权限。
- 手动查看当前版本：`sqlite3 reminders.db "SELECT version FROM schema_version;"`
- 若迁移中断，优先执行备份并保留现场，不建议直接删除 `schema_version` 表。
- 建议流程：备份当前库 -> 在副本中验证迁移修复 -> 再执行恢复或替换。

## 内存占用过高

- 检查提醒数量是否过多（超过 10 万条建议迁移外部数据库）。
- 降低 `SCHEDULER_BATCH_SIZE` 减少单次加载量。
- 定期清理已完成的非重复提醒。

## AI 解析超时

- 默认超时 15 秒，网络不稳定时可能失败。
- 若同时出现 `scheduler_status=processing_failed`，可适当调大 `SCHEDULER_SEND_TIMEOUT_SECONDS`（例如 30-60 秒）。
- 检查 `AI_BASE_URL` 是否可访问。
- 超时后会自动回退到规则解析器。

## 提醒重复发送

- 检查是否有多个实例同时运行（应启用实例锁）。
- 确认 `SCHEDULER_LOCK_SECONDS` 大于单批处理时间。
- 查看日志中是否有锁获取失败的记录。
