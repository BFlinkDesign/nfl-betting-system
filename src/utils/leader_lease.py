"""File-based advisory leader lease for single-instance enforcement.

Prevents duplicate orchestrators or daily pipelines from running
simultaneously. Uses a lockfile with PID + heartbeat timestamp.
"""

import json
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class LeaderLease:
    """File-based advisory lock with heartbeat expiry."""

    def __init__(
        self,
        name: str,
        lock_dir: str = "data",
        ttl_seconds: int = 120,
    ):
        self._name = name
        self._lock_path = Path(lock_dir) / f".{name}.lock"
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._ttl = ttl_seconds
        self._held = False

    def acquire(self) -> bool:
        """Try to acquire the lease. Returns True if acquired."""
        if self._lock_path.exists():
            try:
                data = json.loads(self._lock_path.read_text())
                pid = data.get("pid", -1)
                heartbeat = data.get("heartbeat", 0)
                age = time.time() - heartbeat

                if age < self._ttl and self._pid_alive(pid):
                    logger.warning(
                        "Lease %s held by PID %d (%.0fs old) — cannot acquire",
                        self._name,
                        pid,
                        age,
                    )
                    return False

                logger.info(
                    "Lease %s expired (age=%.0fs, pid=%d alive=%s) — taking over",
                    self._name,
                    age,
                    pid,
                    self._pid_alive(pid),
                )
            except (json.JSONDecodeError, KeyError, OSError):
                logger.warning("Corrupt lease file for %s — overwriting", self._name)

        self._write_lease()
        self._held = True
        logger.info("Acquired lease: %s (PID %d)", self._name, os.getpid())
        return True

    def renew(self) -> None:
        """Update the heartbeat timestamp (call periodically from owner)."""
        if self._held:
            self._write_lease()

    def release(self) -> None:
        """Release the lease."""
        if self._held:
            try:
                self._lock_path.unlink(missing_ok=True)
            except OSError as e:
                logger.warning("Failed to release lease %s: %s", self._name, e)
            self._held = False
            logger.info("Released lease: %s", self._name)

    @property
    def is_held(self) -> bool:
        return self._held

    def _write_lease(self) -> None:
        self._lock_path.write_text(
            json.dumps(
                {"pid": os.getpid(), "heartbeat": time.time(), "name": self._name}
            )
        )

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError(f"Could not acquire lease: {self._name}")
        return self

    def __exit__(self, *args):
        self.release()

    def __del__(self):
        if self._held:
            self.release()
