# 变更记录

## [0.3.5] - 2026-02-08

### Added
- 健康检查服务新增请求读取超时与最大请求头数量限制，降低恶意/异常连接导致的资源占用风险
- 备份脚本新增参数与输出路径校验测试、备份文件权限校验测试

### Changed
- 备份脚本对 `--keep` 增加非负校验，输出路径仅允许目录，备份文件权限默认设置为 `600`

### Documentation
- 部署与运行文档补充备份参数边界、备份文件权限及健康检查防护行为说明

## [0.3.4] - 2026-02-08

### Changed
- 启动阶段对数据库初始化、调度器启动、健康检查启动增加显式异常处理，避免“部分启动成功”状态
- 调度器支持重复启动保护，停止时改为非阻塞关闭（`shutdown(wait=False)`）
- 配置校验增强：`LOG_LEVEL` 标准化与白名单校验、`SCHEDULER_SEND_CONCURRENCY` 上限校验、`HEALTHCHECK_PATH` 空格校验

### Fixed
- 健康检查端口启动失败时补充调度器回收，避免孤儿调度任务残留
- 实例锁支持 `~` 路径展开，并对目录创建/文件打开失败给出明确日志与失败返回
- 清理测试文件中的无用导入，保证 `ruff check` 全量通过

### Added
- 新增启动与关闭异常路径测试（`tests/test_main.py`）
- 新增健康检查 `HEAD` 无响应体测试、实例锁 `~` 路径测试、调度器重复启动保护测试
- 新增配置边界测试（日志级别、健康检查路径空格、发送并发上限）

## [0.3.3] - 2026-01-06

### Added
- 发送尝试字段（send_attempt_for / send_attempt_until）与索引，降低崩溃后的重复发送
- /list 支持分页参数与默认分页大小
- UTF-16 安全截断工具函数，避免消息超过 Telegram 限制

### Changed
- 调度器发送前标记尝试并刷新锁，发送后清理尝试状态
- Reminder 计算下次时间时支持快速追赶，减少大延迟场景循环
- API 文档与 README 同步分页与新字段说明

### Fixed
- 超长内容导致回复失败的问题（创建回执与列表输出）

## [0.3.2] - 2026-01-05

### Changed
- 完善运维手册，补充日志管理、监控告警、性能调优章节
- 故障排查文档新增数据库迁移失败、内存占用过高等场景
- 补充源代码关键函数的文档字符串

### Documentation
- OPERATIONS.md 新增日志轮转、Prometheus 指标、性能调优建议
- TROUBLESHOOTING.md 新增迁移失败、内存问题、AI 超时排查
- 源代码模块补充 docstring 说明

## [0.3.1] - 2025-01-05

### Changed
- 完善所有文档，补充缺失的配置项说明
- README.md 补充 AI_BASE_URL、OPENAI_BASE_URL、ANTHROPIC_BASE_URL 配置
- API.md 补充 claim_pending_reminders 方法和新增字段
- ARCHITECTURE.md 补充 utils 模块说明
- DEVELOPMENT.md 补充完整环境变量列表
- DEPLOYMENT.md 新增 Docker 部署章节
- OPERATIONS.md 新增 Docker 运维命令
- TROUBLESHOOTING.md 新增限流和 Forbidden 故障排查

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
