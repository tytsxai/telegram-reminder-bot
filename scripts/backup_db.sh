#!/usr/bin/env bash
# SQLite 热备份脚本
# 用法: ./scripts/backup_db.sh [DB_PATH] [BACKUP_DIR]
# 环境变量: DATABASE_PATH, BACKUP_DIR, BACKUP_KEEP_DAYS
# 示例: DATABASE_PATH=/app/data/reminders.db BACKUP_DIR=/backups ./scripts/backup_db.sh

set -euo pipefail

DB_PATH="${1:-${DATABASE_PATH:-reminders.db}}"
BACKUP_DIR="${2:-${BACKUP_DIR:-./backups}}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-7}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/reminders_${TIMESTAMP}.db"

if [ ! -f "${DB_PATH}" ]; then
  echo "ERROR: Database file not found: ${DB_PATH}" >&2
  exit 1
fi

mkdir -p "${BACKUP_DIR}"

# 使用 SQLite .backup 命令做热备份（安全，不锁库）
sqlite3 "${DB_PATH}" ".backup '${BACKUP_FILE}'"

echo "Backup created: ${BACKUP_FILE} ($(du -sh "${BACKUP_FILE}" | cut -f1))"

# 清理超过保留天数的旧备份
if command -v find &>/dev/null; then
  find "${BACKUP_DIR}" -name 'reminders_*.db' -mtime "+${KEEP_DAYS}" -delete 2>/dev/null && \
    echo "Cleaned up backups older than ${KEEP_DAYS} days"
fi
