"""Process-level instance lock.

通过文件锁确保同一时间只有一个实例运行，防止重复发送提醒。
支持 Unix (fcntl) 和 Windows (msvcrt) 平台。
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class InstanceLock:
    """Acquire an exclusive lock file to ensure single instance."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._fh: Optional[object] = None

    def acquire(self) -> bool:
        """Acquire the lock file. Returns True on success."""
        if not self.path:
            logger.error("Instance lock path is empty")
            return False
        lock_path = os.path.expanduser(self.path)
        dir_name = os.path.dirname(lock_path)
        if dir_name:
            try:
                os.makedirs(dir_name, exist_ok=True)
            except OSError as exc:
                logger.error(
                    "Failed to create instance lock directory %s: %s", dir_name, exc
                )
                return False
        try:
            self._fh = open(lock_path, "a+", encoding="utf-8")
        except OSError as exc:
            logger.error("Failed to open instance lock file %s: %s", lock_path, exc)
            return False
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._fh.seek(0)
            self._fh.truncate()
            self._fh.write(str(os.getpid()))
            self._fh.flush()
            return True
        except Exception as exc:
            logger.error("Instance lock acquisition failed: %s", exc)
            try:
                self._fh.close()
            except Exception:
                pass
            self._fh = None
            return False

    def release(self) -> None:
        """Release the lock file."""
        if not self._fh:
            return
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            self._fh.close()
        except Exception:
            pass
        self._fh = None
