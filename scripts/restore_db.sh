#!/usr/bin/env bash
# SQLite 数据库恢复脚本
# 用法: ./scripts/restore_db.sh <BACKUP_FILE> [DB_PATH]
# 示例: ./scripts/restore_db.sh backups/reminders_20240101_120000.db /app/data/reminders.db

set -euo pipefail

BACKUP_FILE="${1:-}"
DB_PATH="${2:-${DATABASE_PATH:-reminders.db}}"

if [ -z "${BACKUP_FILE}" ]; then
  echo "Usage: $0 <BACKUP_FILE> [DB_PATH]" >&2
  exit 1
fi

if [ ! -f "${BACKUP_FILE}" ]; then
  echo "ERROR: Backup file not found: ${BACKUP_FILE}" >&2
  exit 1
fi

# 验证备份文件完整性
if ! sqlite3 "${BACKUP_FILE}" 'PRAGMA integrity_check;' | grep -q 'ok'; then
  echo "ERROR: Backup file integrity check failed: ${BACKUP_FILE}" >&2
  exit 1
fi

if [ -f "${DB_PATH}" ]; then
  CURRENT_BACKUP="${DB_PATH}.pre-restore.$(date +%Y%m%d_%H%M%S)"
  cp "${DB_PATH}" "${CURRENT_BACKUP}"
  echo "Current database backed up to: ${CURRENT_BACKUP}"
fi

cp "${BACKUP_FILE}" "${DB_PATH}"
chmod 600 "${DB_PATH}"
echo "Database restored from: ${BACKUP_FILE} -> ${DB_PATH}"
