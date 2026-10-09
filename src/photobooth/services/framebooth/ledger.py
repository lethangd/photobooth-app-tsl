"""Business log of the kiosk: paid sessions, staff PIN confirmations and prints.

Kept in its own small SQLite file (``database/kiosk_ledger.sqlite``) so revenue reporting
does not depend on the media database migrations. All amounts are computed on the server
from ``appconfig.framebooth`` prices, never trusted from the kiosk.
"""

import logging
import sqlite3
import threading
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

from ... import DATABASE_PATH

logger = logging.getLogger(__name__)

PinPurpose = Literal["package", "retake"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id     TEXT PRIMARY KEY,
    created_at     TEXT NOT NULL,
    slot_count     INTEGER NOT NULL,
    package_price  INTEGER NOT NULL,
    retake_shots   INTEGER NOT NULL DEFAULT 0,
    retake_amount  INTEGER NOT NULL DEFAULT 0,
    digital        INTEGER,
    printed_at     TEXT,
    mediaitem_id   TEXT,
    cloud_url      TEXT
);
CREATE TABLE IF NOT EXISTS pin_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,
    session_id  TEXT,
    purpose     TEXT NOT NULL,
    amount      INTEGER NOT NULL,
    ok          INTEGER NOT NULL,
    locked      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_pin_events_created ON pin_events(created_at);
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _day_bounds(day: date) -> tuple[str, str]:
    start = datetime.combine(day, datetime.min.time())
    return start.isoformat(timespec="seconds"), (start + timedelta(days=1)).isoformat(timespec="seconds")


class KioskLedger:
    def __init__(self, path: Path | None = None):
        self._path = path or Path(DATABASE_PATH, "kiosk_ledger.sqlite")
        self._lock = threading.Lock()
        self._initialized = False

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        if not self._initialized:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            connection.executescript(_SCHEMA)
            self._initialized = True
        return connection

    # ───────── writes ─────────

    def record_pin(self, session_id: str | None, purpose: PinPurpose, amount: int, ok: bool, locked: bool = False) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO pin_events (created_at, session_id, purpose, amount, ok, locked) VALUES (?, ?, ?, ?, ?, ?)",
                (_now(), session_id, purpose, amount, int(ok), int(locked)),
            )

    def record_package_paid(self, session_id: str, slot_count: int, price: int) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                """INSERT INTO sessions (session_id, created_at, slot_count, package_price) VALUES (?, ?, ?, ?)
                   ON CONFLICT(session_id) DO UPDATE SET slot_count = excluded.slot_count, package_price = excluded.package_price""",
                (session_id, _now(), slot_count, price),
            )

    def record_retake_paid(self, session_id: str, shots: int, amount: int) -> None:
        with self._lock, self._connect() as db:
            updated = db.execute(
                "UPDATE sessions SET retake_shots = retake_shots + ?, retake_amount = retake_amount + ? WHERE session_id = ?",
                (shots, amount, session_id),
            ).rowcount
            if not updated:  # retake for a session we did not see being paid (e.g. after a restart)
                db.execute(
                    "INSERT INTO sessions (session_id, created_at, slot_count, package_price, retake_shots, retake_amount) VALUES (?, ?, 0, 0, ?, ?)",
                    (session_id, _now(), shots, amount),
                )

    def record_print(self, session_id: str | None, mediaitem_id: str, digital: bool, cloud_url: str | None) -> None:
        if not session_id:
            return
        with self._lock, self._connect() as db:
            db.execute(
                "UPDATE sessions SET printed_at = ?, mediaitem_id = ?, digital = ?, cloud_url = ? WHERE session_id = ?",
                (_now(), mediaitem_id, int(digital), cloud_url, session_id),
            )

    # ───────── reads ─────────

    def sessions(self, day: date, limit: int = 200, offset: int = 0) -> list[dict]:
        start, end = _day_bounds(day)
        with self._lock, self._connect() as db:
            rows = db.execute(
                "SELECT * FROM sessions WHERE created_at >= ? AND created_at < ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (start, end, limit, offset),
            ).fetchall()
        return [
            {
                **dict(row),
                "total": row["package_price"] + row["retake_amount"],
                "digital": None if row["digital"] is None else bool(row["digital"]),
            }
            for row in rows
        ]

    def pin_events(self, day: date, limit: int = 200) -> list[dict]:
        start, end = _day_bounds(day)
        with self._lock, self._connect() as db:
            rows = db.execute(
                "SELECT * FROM pin_events WHERE created_at >= ? AND created_at < ? ORDER BY id DESC LIMIT ?",
                (start, end, limit),
            ).fetchall()
        return [{**dict(row), "ok": bool(row["ok"]), "locked": bool(row["locked"])} for row in rows]

    def day_stats(self, day: date) -> dict:
        return self.period_stats(day, day)

    def period_stats(self, first: date, last: date) -> dict:
        """Totals from ``first`` to ``last`` (both included)."""
        start, _ = _day_bounds(first)
        _, end = _day_bounds(last)
        with self._lock, self._connect() as db:
            sessions = db.execute("SELECT * FROM sessions WHERE created_at >= ? AND created_at < ?", (start, end)).fetchall()
            pins = db.execute("SELECT ok, locked FROM pin_events WHERE created_at >= ? AND created_at < ?", (start, end)).fetchall()

        revenue = sum(row["package_price"] + row["retake_amount"] for row in sessions)
        by_hour = Counter(int(row["created_at"][11:13]) for row in sessions)
        revenue_by_hour: Counter[int] = Counter()
        for row in sessions:
            revenue_by_hour[int(row["created_at"][11:13])] += row["package_price"] + row["retake_amount"]
        packages = Counter(row["slot_count"] for row in sessions if row["slot_count"])

        return {
            "day": last.isoformat(),
            "first_day": first.isoformat(),
            "sessions": len(sessions),
            "revenue": revenue,
            "printed": sum(1 for row in sessions if row["printed_at"]),
            "retake_revenue": sum(row["retake_amount"] for row in sessions),
            "retake_shots": sum(row["retake_shots"] for row in sessions),
            "digital": sum(1 for row in sessions if row["digital"]),
            "average_ticket": round(revenue / len(sessions)) if sessions else 0,
            "pin_ok": sum(1 for row in pins if row["ok"]),
            "pin_failed": sum(1 for row in pins if not row["ok"]),
            "pin_locked": sum(1 for row in pins if row["locked"]),
            "by_hour": [{"hour": hour, "sessions": by_hour.get(hour, 0), "revenue": revenue_by_hour.get(hour, 0)} for hour in range(24)],
            "by_package": [{"slot_count": slots, "sessions": count} for slots, count in sorted(packages.items())],
        }

    def session(self, session_id: str) -> dict | None:
        with self._lock, self._connect() as db:
            row = db.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
            pins = db.execute("SELECT * FROM pin_events WHERE session_id = ? ORDER BY id", (session_id,)).fetchall()
        if not row:
            return None
        return {
            **dict(row),
            "total": row["package_price"] + row["retake_amount"],
            "digital": None if row["digital"] is None else bool(row["digital"]),
            "pin_events": [{**dict(pin), "ok": bool(pin["ok"]), "locked": bool(pin["locked"])} for pin in pins],
        }

    def daily_series(self, days: int, until: date) -> list[dict]:
        first = until - timedelta(days=days - 1)
        start, _ = _day_bounds(first)
        _, end = _day_bounds(until)
        with self._lock, self._connect() as db:
            rows = db.execute(
                """SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS sessions, SUM(package_price + retake_amount) AS revenue
                   FROM sessions WHERE created_at >= ? AND created_at < ? GROUP BY day""",
                (start, end),
            ).fetchall()
        found = {row["day"]: row for row in rows}
        series = []
        for offset in range(days):
            key = (first + timedelta(days=offset)).isoformat()
            row = found.get(key)
            series.append({"day": key, "sessions": row["sessions"] if row else 0, "revenue": (row["revenue"] or 0) if row else 0})
        return series


ledger = KioskLedger()
