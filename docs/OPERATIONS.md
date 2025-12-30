# 生产运行手册

## 启动/停止

### 直接运行

```bash
source venv/bin/activate
python main.py
```

### systemd

参见 `docs/DEPLOYMENT.md` 中的 systemd 示例。

## 运行检查清单

- `.env` 已配置并可读取
- `BOT_TOKEN` 正确
- `DATABASE_PATH` 指向可写路径
- 仅单实例运行（默认启用实例锁）
- 健康检查开启（可选）

## 备份

使用内置脚本：

```bash
python scripts/backup_db.py --db /path/to/reminders.db --out-dir /var/backups/reminder --keep 7
```

建议通过 cron 或 systemd timer 定时执行。

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
