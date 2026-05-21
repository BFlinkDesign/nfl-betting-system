"""Tests for production hardening: leader lease, logging, health, startup."""

import json
import logging
import os
import time

import pytest

from src.config.logging_config import HumanFormatter, JSONFormatter, setup_logging
from src.config.startup import startup_check, validate_config, validate_dependencies
from src.utils.leader_lease import LeaderLease


class TestLeaderLease:
    def test_acquire_and_release(self, tmp_path):
        lease = LeaderLease("test_leader", lock_dir=str(tmp_path), ttl_seconds=10)
        assert lease.acquire()
        assert lease.is_held
        assert (tmp_path / ".test_leader.lock").exists()

        lease.release()
        assert not lease.is_held
        assert not (tmp_path / ".test_leader.lock").exists()

    def test_double_acquire_same_pid(self, tmp_path):
        l1 = LeaderLease("test_dup", lock_dir=str(tmp_path), ttl_seconds=60)
        l2 = LeaderLease("test_dup", lock_dir=str(tmp_path), ttl_seconds=60)

        assert l1.acquire()
        assert not l2.acquire()

        l1.release()
        assert l2.acquire()
        l2.release()

    def test_expired_lease_takeover(self, tmp_path):
        lock_path = tmp_path / ".test_expired.lock"
        lock_path.write_text(
            json.dumps({"pid": 999999, "heartbeat": time.time() - 200})
        )

        lease = LeaderLease("test_expired", lock_dir=str(tmp_path), ttl_seconds=10)
        assert lease.acquire()
        lease.release()

    def test_context_manager(self, tmp_path):
        with LeaderLease("test_ctx", lock_dir=str(tmp_path)) as lease:
            assert lease.is_held
        assert not lease.is_held

    def test_context_manager_failure(self, tmp_path):
        lock_path = tmp_path / ".test_block.lock"
        lock_path.write_text(json.dumps({"pid": os.getpid(), "heartbeat": time.time()}))

        with pytest.raises(RuntimeError, match="Could not acquire"):
            with LeaderLease("test_block", lock_dir=str(tmp_path), ttl_seconds=60):
                pass

    def test_renew(self, tmp_path):
        lease = LeaderLease("test_renew", lock_dir=str(tmp_path))
        lease.acquire()
        lock_path = tmp_path / ".test_renew.lock"
        t1 = json.loads(lock_path.read_text())["heartbeat"]
        time.sleep(0.05)
        lease.renew()
        t2 = json.loads(lock_path.read_text())["heartbeat"]
        assert t2 > t1
        lease.release()


class TestJSONFormatter:
    def test_json_output(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello world",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["msg"] == "hello world"
        assert parsed["level"] == "INFO"
        assert "ts" in parsed


class TestSetupLogging:
    def test_human_format(self):
        setup_logging(level="DEBUG", json_format=False)
        root = logging.getLogger()
        assert any(isinstance(h.formatter, HumanFormatter) for h in root.handlers)

    def test_json_format(self):
        setup_logging(level="INFO", json_format=True)
        root = logging.getLogger()
        assert any(isinstance(h.formatter, JSONFormatter) for h in root.handlers)

    def test_file_logging(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        setup_logging(level="INFO", log_file=log_file)
        logging.getLogger("test_file").info("file log test")
        assert (tmp_path / "test.log").exists()


class TestStartupCheck:
    def test_validate_dependencies(self):
        assert validate_dependencies() is True

    def test_validate_config(self):
        assert validate_config() is True

    def test_startup_check_passes(self):
        assert startup_check() is True


class TestHealthAPI:
    def test_live_endpoint(self):
        from fastapi.testclient import TestClient

        from src.health.api import app

        client = TestClient(app)
        resp = client.get("/live")
        assert resp.status_code == 200
        assert resp.json()["alive"] is True

    def test_ready_endpoint(self):
        from fastapi.testclient import TestClient

        from src.health.api import app

        client = TestClient(app)
        resp = client.get("/ready")
        assert resp.status_code == 200

    def test_health_endpoint(self):
        from fastapi.testclient import TestClient

        from src.health.api import app

        client = TestClient(app)
        resp = client.get("/health")
        data = resp.json()
        assert "status" in data
        assert "checks" in data
        assert "uptime_seconds" in data
