# AGENTS.md

> 目标：让后来者在 1 分钟内看懂项目骨架、职责边界、上线必经流程。

## 1) 目录骨架（当前）

```text
智能提醒机器人/
├── main.py                      # 进程入口：启动 Bot / Scheduler / HealthCheck / 实例锁
├── src/
│   ├── config.py                # 配置装载与合法性校验（pydantic-settings）
│   ├── bot/
│   │   ├── handlers.py          # Telegram handler 注册
│   │   └── commands.py          # /start /help /remind /list /delete 与自然语言入口
│   ├── database/
│   │   └── db.py                # SQLite 访问层：DDL、迁移、查询、领取、更新
│   ├── models/
│   │   └── reminder.py          # Reminder 数据模型与 RepeatType
│   ├── services/
│   │   ├── ai_parser.py         # 规则解析 + 多 LLM 解析器（失败自动回退规则）
│   │   ├── reminder.py          # 提醒业务逻辑（创建/删除/重复时间推进）
│   │   ├── scheduler.py         # 调度发送、限流处理、失败退避、健康快照
│   │   └── healthcheck.py       # 轻量 HTTP 健康探针
│   └── utils/
│       ├── time_utils.py        # 时区/UTC转换、月份推进
│       ├── text_utils.py        # UTF-16 长度控制（Telegram 4096 上限）
│       └── instance_lock.py     # 单实例文件锁
├── scripts/
│   ├── preflight.py             # 上线前 Gate（配置/路径/锁/DB/权限/运行风险）
│   ├── backup_db.py             # SQLite 备份（含 quick_check）
│   └── restore_db.py            # SQLite 恢复（先快照再原子替换）
├── docs/
│   ├── DEPLOYMENT.md            # 部署与发布前检查
│   ├── OPERATIONS.md            # 运行手册、告警、回滚
│   ├── TROUBLESHOOTING.md       # 故障排查
│   └── ARCHITECTURE.md          # 架构说明
├── tests/                       # 单元/集成测试
├── Dockerfile                   # 容器镜像定义（非 root）
└── docker-compose.yml           # 运行编排与健康检查
```

## 2) 模块职责与边界

- `bot/*` 只处理交互协议，不持有持久化细节。
- `services/*` 只承载业务规则，不直接依赖 Telegram 具体 handler。
- `database/db.py` 是唯一 SQLite 访问入口（Single Source of Truth）。
- `scripts/*` 是运维入口：发布前检查、备份、恢复，不混入业务代码。
- `main.py` 仅做组装（composition root），不写业务逻辑。

## 3) 关键依赖关系（上游 -> 下游）

```text
main.py
  -> src.bot.handlers
  -> src.services.scheduler
  -> src.services.healthcheck
  -> src.database.db

src.bot.commands
  -> src.services.reminder
  -> src.services.ai_parser

src.services.reminder
  -> src.database.db

src.services.scheduler
  -> src.database.db
  -> src.services.reminder

scripts/preflight.py
  -> src.config / src.database.db / src.utils.instance_lock
```

约束：
- `services` 不反向 import `bot`。
- `database` 不反向依赖 `services`。
- `scripts` 可依赖应用模块，但应用运行时不依赖 `scripts`。

## 4) 生产运行红线

1. **单实例红线**：`INSTANCE_LOCK_ENABLED=true`（默认开启）。
2. **数据完整性红线**：`DB_QUICK_CHECK_ON_STARTUP=true`（建议保持开启）。
3. **可观测性红线**：`HEALTHCHECK_ENABLED=true`（生产建议必须开启）。
4. **发布门禁红线**：发布前必须执行 `python scripts/preflight.py`。
5. **强门禁模式**：CI/CD 建议使用 `--strict-warnings`。
6. **发送超时红线**：`SCHEDULER_SEND_TIMEOUT_SECONDS` 必须 `<= SCHEDULER_LOCK_SECONDS`（配置已强校验）。

## 5) 上线最小闭环

```bash
# 1) 依赖与测试
pip install -r requirements.lock
pytest -q

# 2) 发布前 Gate（建议严格模式）
python scripts/preflight.py --strict-warnings

# 3) 启动
python main.py

# 4) 探针验证
curl http://127.0.0.1:8080/healthz
```

## 6) 近期变更（2026-02-25）

- 健康检查默认基线调整：`HEALTHCHECK_ENABLED` 默认值调整为 `true`，降低“误关探针直接上线”的风险。
- preflight 补强：
  - 新增健康检查端口可绑定校验（`HEALTHCHECK_HOST:HEALTHCHECK_PORT` 冲突会直接阻断）；
  - 新增 `.env` 重复键告警，降低配置被覆盖导致的发布偏差；
  - 新增参数 `--healthcheck-host`、`--healthcheck-port`，便于 CI/CD 固化探针绑定检查。
- 优雅停机补强：
  - 调度器 `stop()` 默认等待在途任务完成，降低停机时重复发送/状态未落库风险；
  - `docker-compose` 新增 `stop_grace_period: 90s`，为优雅停机保留窗口。

## 6.1) 历史变更（2026-02-12）

- 调度器发送超时补强：新增 `SCHEDULER_SEND_TIMEOUT_SECONDS`，单次发送超时会被中断并设置重试窗口，避免线程悬挂拖垮调度循环。
- 调度器健康判断补强：
  - 连续领取失败达到阈值会判定不健康（`consecutive_claim_failures`）；
  - 连续处理失败达到阈值会判定不健康（`consecutive_process_failures`）。
- 健康检查补强：
  - DB ping 异常与超时都显式进入 payload（`db_status`）；
  - 调度器不健康原因显式进入 payload（`scheduler_status`，新增 `processing_failed`）。
- Docker 运行基线补强：`docker-compose` 默认将 `INSTANCE_LOCK_PATH` 指向 `/app/data/reminder-bot.lock`，兼容只读根文件系统。
- 数据文件权限补强：数据库初始化会将 SQLite 文件权限收敛为 `600`；preflight 在 runtime check 后再评估权限，减少误报。
- preflight 补强：
  - `BOT_TOKEN` 格式非法直接阻断；
  - 新增 `--strict-warnings`，可将 warning 作为发布阻断。
- CI 补强：新增 lint + preflight gate。
- 文档补强：README/部署/运维/排障/API 已对齐发送超时、健康状态与权限基线。

## 7) 文档同步原则

- 任何运行策略、发布门禁、健康字段变化，都必须同步更新：
  - `README.md`
  - `docs/DEPLOYMENT.md`
  - `docs/OPERATIONS.md`
  - `docs/TROUBLESHOOTING.md`
  - 本 `AGENTS.md`
