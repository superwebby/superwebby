"""Visit history, closed-tab stack, and quiet session restore."""

from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Visit:
    url: str
    title: str
    last_visited: float
    count: int


@dataclass
class ClosedTab:
    url: str
    title: str


class HistoryStore:
    def __init__(self, path: Path, enabled: bool = True) -> None:
        self.enabled = enabled
        self.path = path
        self._lock = threading.Lock()
        self._closed: list[ClosedTab] = []
        if not enabled:
            self.conn: sqlite3.Connection | None = None
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS visits (
                url TEXT PRIMARY KEY,
                title TEXT,
                last_visited REAL,
                count INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_visits_last ON visits(last_visited DESC);
            CREATE TABLE IF NOT EXISTS session_tabs (
                tab_index INTEGER PRIMARY KEY,
                url TEXT,
                title TEXT,
                active INTEGER
            );
            """
        )
        self.conn.commit()

    def record(self, url: str, title: str) -> None:
        if not self.enabled or not self.conn or not url:
            return
        if url.startswith("superwebby://"):
            return
        title = title or url
        now = time.time()
        with self._lock:
            self.conn.execute(
                """
                INSERT INTO visits(url, title, last_visited, count)
                VALUES(?, ?, ?, 1)
                ON CONFLICT(url) DO UPDATE SET
                    title=excluded.title,
                    last_visited=excluded.last_visited,
                    count=visits.count + 1
                """,
                (url, title, now),
            )
            self.conn.commit()

    def search(self, query: str, limit: int = 30) -> list[Visit]:
        if not self.enabled or not self.conn:
            return []
        q = f"%{query.strip()}%" if query.strip() else None
        with self._lock:
            if q:
                rows = self.conn.execute(
                    """
                    SELECT url, title, last_visited, count FROM visits
                    WHERE url LIKE ? OR title LIKE ?
                    ORDER BY last_visited DESC LIMIT ?
                    """,
                    (q, q, limit),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    """
                    SELECT url, title, last_visited, count FROM visits
                    ORDER BY last_visited DESC LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [Visit(*row) for row in rows]

    def frequent(self, limit: int = 8) -> list[Visit]:
        if not self.enabled or not self.conn:
            return []
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT url, title, last_visited, count FROM visits
                ORDER BY count DESC, last_visited DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [Visit(*row) for row in rows]

    def recent(self, limit: int = 50) -> list[Visit]:
        return self.search("", limit=limit)

    def clear(self) -> None:
        if not self.conn:
            return
        with self._lock:
            self.conn.execute("DELETE FROM visits")
            self.conn.commit()

    def push_closed(self, url: str, title: str) -> None:
        if not url:
            return
        self._closed.append(ClosedTab(url=url, title=title or url))
        if len(self._closed) > 50:
            self._closed = self._closed[-50:]

    def pop_closed(self) -> ClosedTab | None:
        if not self._closed:
            return None
        return self._closed.pop()

    def save_session(self, tabs: list[tuple[str, str, bool]]) -> None:
        if not self.enabled or not self.conn:
            return
        with self._lock:
            self.conn.execute("DELETE FROM session_tabs")
            for index, (url, title, active) in enumerate(tabs):
                self.conn.execute(
                    "INSERT INTO session_tabs(tab_index, url, title, active) VALUES(?,?,?,?)",
                    (index, url, title, 1 if active else 0),
                )
            self.conn.commit()

    def load_session(self) -> list[tuple[str, str, bool]]:
        if not self.enabled or not self.conn:
            return []
        with self._lock:
            rows = self.conn.execute(
                "SELECT url, title, active FROM session_tabs ORDER BY tab_index"
            ).fetchall()
        return [(url, title or url, bool(active)) for url, title, active in rows if url]

    def close(self) -> None:
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
