"""Instance lock tests."""

import os

import pytest

from src.utils.instance_lock import InstanceLock


def test_instance_lock_acquire_release(tmp_path):
    lock_path = tmp_path / "lockfile"
    lock = InstanceLock(str(lock_path))
    assert lock.acquire() is True
    assert lock_path.exists()
    lock.release()


def test_instance_lock_creates_directory(tmp_path):
    lock_path = tmp_path / "locks" / "lockfile"
    lock = InstanceLock(str(lock_path))
    assert lock.acquire() is True
    assert lock_path.exists()
    lock.release()


def test_instance_lock_empty_path():
    lock = InstanceLock("")
    assert lock.acquire() is False


def test_instance_lock_release_without_acquire():
    lock = InstanceLock("unused.lock")
    lock.release()


def test_instance_lock_acquire_failure(monkeypatch, tmp_path):
    if os.name == "nt":
        pytest.skip("POSIX-only test")
    import fcntl

    lock_path = tmp_path / "lockfile"
    lock = InstanceLock(str(lock_path))

    def _fail(*args, **kwargs):
        raise OSError("fail")

    monkeypatch.setattr(fcntl, "flock", _fail)
    assert lock.acquire() is False


def test_instance_lock_release_failure(monkeypatch, tmp_path):
    if os.name == "nt":
        pytest.skip("POSIX-only test")
    import fcntl

    lock_path = tmp_path / "lockfile"
    lock = InstanceLock(str(lock_path))
    lock._fh = open(lock_path, "a+", encoding="utf-8")

    def _fail(*args, **kwargs):
        raise OSError("fail")

    monkeypatch.setattr(fcntl, "flock", _fail)
    lock.release()
