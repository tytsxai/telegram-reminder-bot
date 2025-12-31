# 变更记录

## [0.3.0] - 2025-12-31

### Added
- 调度批量/锁定/并发配置项
- Docker 部署文件（Dockerfile / docker-compose / .dockerignore）
- 提醒锁与发送时间字段（locked_until / last_sent_at / last_sent_for）

### Changed
- 调度器改为批量领取+锁定，避免并发重复发送
- 启动时注册 Telegram 命令列表
- 删除提醒时限定 chat_id，避免跨会话误删
- 时间存储统一为 UTC（含迁移）

### Fixed
- 明确日期但已过期的提醒解析返回失败

## [0.2.1] - 2025-12-30

### Added
- 实例锁防止多进程重复运行
- 备份脚本与运行手册文档
- 运行日志补充（创建/发送提醒）

### Changed
- 部署文档增加备份/恢复流程

## [0.2.0] - 2025-12-30

### Added
- 新增健康检查 HTTP 服务与配置项
- 新增 OpenAI/Claude 解析器与默认解析器选择逻辑
- 数据库 schema_version 版本表与索引迁移
- 生产部署与故障排查文档

### Changed
- 配置项扩展（日志、调度间隔、AI Provider）
- 调度器支持配置化扫描间隔

### Fixed
- 配置默认值与验证逻辑统一
