# 故障排查指南

## 启动失败 / 机器人无响应

- 检查 `BOT_TOKEN` 是否配置正确。
- 确认网络能够访问 Telegram。
- 查看日志是否包含 `BOT_TOKEN not configured`。

## 实例锁导致无法启动

- 日志出现 `Another instance is running` 表示已有实例在运行。
- 确认只启动了一个进程，或关闭旧进程后重启。

## 健康检查 503

- 代表依赖（数据库等）不可用。
- 检查数据库路径是否可写，磁盘空间是否充足。
- 查看日志中的 `db_error` 或数据库异常信息。

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
