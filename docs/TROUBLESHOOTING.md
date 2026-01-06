# 故障排查指南

## 启动失败 / 机器人无响应

- 检查 `BOT_TOKEN` 是否配置正确。
- 确认网络能够访问 Telegram。
- 查看日志是否包含 `BOT_TOKEN not configured`。

## 实例锁导致无法启动

- 日志出现 `Another instance is running` 表示已有实例在运行。
- 确认只启动了一个进程，或关闭旧进程后重启。

## 健康检查 503

- 代表依赖不可用（数据库或调度器异常）。
- 检查数据库路径是否可写，磁盘空间是否充足。
- 若返回 `scheduler_unhealthy`，检查调度器是否卡住或事件循环阻塞。
- 查看日志中的 `db_error` / `scheduler_unhealthy` 相关信息。

## 时区报错

- `Invalid TIMEZONE` 表示时区名称不合法。
- 使用标准 IANA 时区名称，例如 `Asia/Shanghai`、`UTC`。

## 数据库锁定 / 无法写入

- 确认数据库文件权限可写。
- 避免多个实例同时写同一个 SQLite 文件。
- 若需多实例部署，建议迁移到外部数据库。

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

## 数据库迁移失败

- 日志出现 `schema_version` 相关错误时，检查数据库文件权限。
- 手动查看当前版本：`sqlite3 reminders.db "SELECT version FROM schema_version;"`
- 若迁移中断，可尝试删除 `schema_version` 表后重启（会重新执行迁移）。

## 内存占用过高

- 检查提醒数量是否过多（超过 10 万条建议迁移外部数据库）。
- 降低 `SCHEDULER_BATCH_SIZE` 减少单次加载量。
- 定期清理已完成的非重复提醒。

## AI 解析超时

- 默认超时 15 秒，网络不稳定时可能失败。
- 检查 `AI_BASE_URL` 是否可访问。
- 超时后会自动回退到规则解析器。

## 提醒重复发送

- 检查是否有多个实例同时运行（应启用实例锁）。
- 确认 `SCHEDULER_LOCK_SECONDS` 大于单批处理时间。
- 查看日志中是否有锁获取失败的记录。
