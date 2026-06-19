"""SQLite-backed dedup store. Tracks which story ids we've already emitted."""
from __future__ import annotations

import sqlite3
from pathlib import Path


class DedupStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                topic TEXT NOT NULL,
                seen_at INTEGER NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS seen_seen_at ON seen(seen_at)"
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "DedupStore":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def is_seen(self, story_id: str, topic: str) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM seen WHERE id = ? AND topic = ? LIMIT 1",
            (story_id, topic),
        )
        return cur.fetchone() is not None

    def mark_seen(self, story_ids: list[str], topic: str, seen_at_ms: int) -> None:
        if not story_ids:
            return
        self._conn.executemany(
            "INSERT OR IGNORE INTO seen(id, source, topic, seen_at) VALUES (?, ?, ?, ?)",
            [(sid, "", topic, seen_at_ms) for sid in story_ids],
        )
        self._conn.commit()

    def vacuum_old(self, older_than_ms: int) -> int:
        cur = self._conn.execute("DELETE FROM seen WHERE seen_at < ?", (older_than_ms,))
        self._conn.commit()
        return cur.rowcount
