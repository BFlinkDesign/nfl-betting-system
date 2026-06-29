"""Persistent event store for agent messages and system audit trail.

Writes every routed message to a SQLite append-only log so that
agent interactions can be replayed, audited, and debugged post-mortem.
"""

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    message_id TEXT NOT NULL,
    sender_id TEXT NOT NULL,
    receiver_id TEXT,
    message_type TEXT NOT NULL,
    priority INTEGER DEFAULT 3,
    parent_id TEXT,
    content TEXT,
    UNIQUE(message_id)
);
CREATE INDEX IF NOT EXISTS idx_events_sender ON events(sender_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(message_type);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(timestamp);
"""


class EventStore:
    """Append-only SQLite event log for agent messages."""

    def __init__(self, db_path: str = "data/events.db"):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.executescript(_CREATE_SQL)
        self._conn.commit()
        logger.info("EventStore initialized at %s", self._db_path)

    def record(self, message) -> None:
        """Persist an AgentMessage to the event log."""
        with self._lock:
            try:
                self._conn.execute(
                    """INSERT OR IGNORE INTO events
                       (timestamp, message_id, sender_id, receiver_id,
                        message_type, priority, parent_id, content)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        (
                            message.timestamp.isoformat()
                            if hasattr(message.timestamp, "isoformat")
                            else str(message.timestamp)
                        ),
                        message.message_id,
                        message.sender_id,
                        message.receiver_id or "",
                        message.message_type,
                        message.priority,
                        message.parent_id or "",
                        json.dumps(message.content, default=str),
                    ),
                )
                self._conn.commit()
            except Exception as e:
                logger.error("EventStore write failed: %s", e)

    def query(
        self,
        sender_id: Optional[str] = None,
        message_type: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """Query events with optional filters."""
        clauses = []
        params = []
        if sender_id:
            clauses.append("sender_id = ?")
            params.append(sender_id)
        if message_type:
            clauses.append("message_type = ?")
            params.append(message_type)
        if since:
            clauses.append("timestamp >= ?")
            params.append(since)

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM events WHERE {where} ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            cursor = self._conn.execute(sql, params)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    def close(self):
        self._conn.close()


_instance: Optional[EventStore] = None


def get_event_store() -> EventStore:
    global _instance
    if _instance is None:
        _instance = EventStore()
    return _instance
