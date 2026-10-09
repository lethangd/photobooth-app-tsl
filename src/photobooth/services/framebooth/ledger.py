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

PinPurpose = Literal["package", "retake", "copies"]
PaymentMethod = Literal["pin", "transfer", "voucher"]

# what a session really brought in: list price minus discount, plus paid retakes and extra copies
TOTAL_SQL = "(package_price - discount + retake_amount + copies_amount)"

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
CREATE TABLE IF NOT EXISTS transfers (
    tx_id       TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    amount      INTEGER NOT NULL,
    content     TEXT NOT NULL,
    reference   TEXT
);
CREATE TABLE IF NOT EXISTS voucher_uses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,
    code        TEXT NOT NULL,
    session_id  TEXT,
    discount    INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS loyalty (
    phone       TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    stamps      INTEGER NOT NULL DEFAULT 0,
    sessions    INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS loyalty_stamps (
    session_id  TEXT PRIMARY KEY,
    phone       TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reward_codes (
    code         TEXT PRIMARY KEY,
    phone        TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    valid_until  TEXT NOT NULL,
    used_at      TEXT,
    used_session TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_pin_events_created ON pin_events(created_at);
CREATE INDEX IF NOT EXISTS idx_voucher_uses_code ON voucher_uses(code);
"""

# columns added after the first release; created on old databases when the ledger opens
_SESSION_COLUMNS = {
    "discount": "INTEGER NOT NULL DEFAULT 0",
    "voucher_code": "TEXT",
    "payment_method": "TEXT",
    "copies": "INTEGER NOT NULL DEFAULT 1",
    "copies_amount": "INTEGER NOT NULL DEFAULT 0",
    "rating": "INTEGER",
    "share_consent": "INTEGER",
    "phone": "TEXT",
    "print_error": "TEXT",
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _total(row: sqlite3.Row) -> int:
    return row["package_price"] - row["discount"] + row["retake_amount"] + row["copies_amount"]


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
            existing = {row["name"] for row in connection.execute("PRAGMA table_info(sessions)")}
            for column, definition in _SESSION_COLUMNS.items():
                if column not in existing:
                    connection.execute(f"ALTER TABLE sessions ADD COLUMN {column} {definition}")
            connection.commit()
            self._initialized = True
        return connection

    # ───────── writes ─────────

    def record_pin(self, session_id: str | None, purpose: PinPurpose, amount: int, ok: bool, locked: bool = False) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO pin_events (created_at, session_id, purpose, amount, ok, locked) VALUES (?, ?, ?, ?, ?, ?)",
                (_now(), session_id, purpose, amount, int(ok), int(locked)),
            )

    def record_package_paid(
        self,
        session_id: str,
        slot_count: int,
        price: int,
        discount: int = 0,
        voucher_code: str | None = None,
        method: PaymentMethod = "pin",
    ) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                """INSERT INTO sessions (session_id, created_at, slot_count, package_price, discount, voucher_code, payment_method)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(session_id) DO UPDATE SET slot_count = excluded.slot_count, package_price = excluded.package_price,
                   discount = excluded.discount, voucher_code = excluded.voucher_code, payment_method = excluded.payment_method""",
                (session_id, _now(), slot_count, price, discount, voucher_code, method),
            )
            if voucher_code and discount:
                db.execute(
                    "INSERT INTO voucher_uses (created_at, code, session_id, discount) VALUES (?, ?, ?, ?)",
                    (_now(), voucher_code, session_id, discount),
                )

    @staticmethod
    def _ensure_session(db: sqlite3.Connection, session_id: str) -> None:
        # extras for a session we did not see being paid (e.g. after a restart)
        db.execute(
            "INSERT OR IGNORE INTO sessions (session_id, created_at, slot_count, package_price) VALUES (?, ?, 0, 0)",
            (session_id, _now()),
        )

    def record_retake_paid(self, session_id: str, shots: int, amount: int) -> None:
        with self._lock, self._connect() as db:
            self._ensure_session(db, session_id)
            db.execute(
                "UPDATE sessions SET retake_shots = retake_shots + ?, retake_amount = retake_amount + ? WHERE session_id = ?",
                (shots, amount, session_id),
            )

    def record_copies_paid(self, session_id: str, extra_copies: int, amount: int) -> None:
        with self._lock, self._connect() as db:
            self._ensure_session(db, session_id)
            db.execute(
                "UPDATE sessions SET copies = copies + ?, copies_amount = copies_amount + ? WHERE session_id = ?",
                (extra_copies, amount, session_id),
            )

    def record_session_field(self, session_id: str, field: Literal["rating", "share_consent", "print_error"], value) -> None:
        if field not in ("rating", "share_consent", "print_error"):
            raise ValueError(field)
        with self._lock, self._connect() as db:
            self._ensure_session(db, session_id)
            db.execute(f"UPDATE sessions SET {field} = ? WHERE session_id = ?", (value, session_id))

    def record_print(self, session_id: str | None, mediaitem_id: str, digital: bool, cloud_url: str | None) -> None:
        if not session_id:
            return
        with self._lock, self._connect() as db:
            db.execute(
                "UPDATE sessions SET printed_at = ?, mediaitem_id = ?, digital = ?, cloud_url = ? WHERE session_id = ?",
                (_now(), mediaitem_id, int(digital), cloud_url, session_id),
            )

    # ───────── bank transfers ─────────

    def record_transfer(self, tx_id: str, amount: int, content: str, reference: str | None) -> bool:
        """Store an incoming transfer once. False when this transaction was already seen."""
        with self._lock, self._connect() as db:
            inserted = db.execute(
                "INSERT OR IGNORE INTO transfers (tx_id, created_at, amount, content, reference) VALUES (?, ?, ?, ?, ?)",
                (tx_id, _now(), amount, content, reference),
            ).rowcount
        return bool(inserted)

    def transfers(self, day: date, limit: int = 200) -> list[dict]:
        start, end = _day_bounds(day)
        with self._lock, self._connect() as db:
            rows = db.execute(
                "SELECT * FROM transfers WHERE created_at >= ? AND created_at < ? ORDER BY created_at DESC LIMIT ?",
                (start, end, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    # ───────── vouchers & loyalty ─────────

    def voucher_use_count(self, code: str) -> int:
        with self._lock, self._connect() as db:
            return db.execute("SELECT COUNT(*) FROM voucher_uses WHERE code = ?", (code,)).fetchone()[0]

    def reward_code(self, code: str) -> dict | None:
        with self._lock, self._connect() as db:
            row = db.execute("SELECT * FROM reward_codes WHERE code = ?", (code,)).fetchone()
        return dict(row) if row else None

    def use_reward_code(self, code: str, session_id: str) -> bool:
        with self._lock, self._connect() as db:
            return bool(
                db.execute(
                    "UPDATE reward_codes SET used_at = ?, used_session = ? WHERE code = ? AND used_at IS NULL",
                    (_now(), session_id, code),
                ).rowcount
            )

    def add_loyalty_stamp(self, phone: str, session_id: str, stamps_for_reward: int, reward_code: str, valid_until: date) -> dict:
        """One stamp per session. When the card is full a free-session code is issued and the card starts over."""
        with self._lock, self._connect() as db:
            now = _now()
            db.execute("INSERT OR IGNORE INTO loyalty (phone, created_at, updated_at) VALUES (?, ?, ?)", (phone, now, now))
            fresh = db.execute(
                "INSERT OR IGNORE INTO loyalty_stamps (session_id, phone, created_at) VALUES (?, ?, ?)", (session_id, phone, now)
            ).rowcount
            if fresh:
                db.execute("UPDATE loyalty SET stamps = stamps + 1, sessions = sessions + 1, updated_at = ? WHERE phone = ?", (now, phone))
                db.execute("UPDATE sessions SET phone = ? WHERE session_id = ?", (phone, session_id))
            row = db.execute("SELECT stamps, sessions FROM loyalty WHERE phone = ?", (phone,)).fetchone()
            stamps, issued = row["stamps"], None
            if fresh and stamps >= stamps_for_reward:
                db.execute(
                    "INSERT INTO reward_codes (code, phone, created_at, valid_until) VALUES (?, ?, ?, ?)",
                    (reward_code, phone, now, valid_until.isoformat()),
                )
                db.execute("UPDATE loyalty SET stamps = 0 WHERE phone = ?", (phone,))
                issued = reward_code
        return {"stamps": stamps, "sessions": row["sessions"], "new_stamp": bool(fresh), "reward_code": issued}

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
                "total": _total(row),
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

        revenue = sum(_total(row) for row in sessions)
        by_hour = Counter(int(row["created_at"][11:13]) for row in sessions)
        revenue_by_hour: Counter[int] = Counter()
        for row in sessions:
            revenue_by_hour[int(row["created_at"][11:13])] += _total(row)
        packages = Counter(row["slot_count"] for row in sessions if row["slot_count"])

        return {
            "day": last.isoformat(),
            "first_day": first.isoformat(),
            "sessions": len(sessions),
            "revenue": revenue,
            "printed": sum(1 for row in sessions if row["printed_at"]),
            "retake_revenue": sum(row["retake_amount"] for row in sessions),
            "retake_shots": sum(row["retake_shots"] for row in sessions),
            "discount": sum(row["discount"] for row in sessions),
            "copies_revenue": sum(row["copies_amount"] for row in sessions),
            "transfer_sessions": sum(1 for row in sessions if row["payment_method"] == "transfer"),
            "ratings": {str(score): sum(1 for row in sessions if row["rating"] == score) for score in (1, 2, 3)},
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
            "total": _total(row),
            "digital": None if row["digital"] is None else bool(row["digital"]),
            "pin_events": [{**dict(pin), "ok": bool(pin["ok"]), "locked": bool(pin["locked"])} for pin in pins],
        }

    def daily_series(self, days: int, until: date) -> list[dict]:
        first = until - timedelta(days=days - 1)
        start, _ = _day_bounds(first)
        _, end = _day_bounds(until)
        with self._lock, self._connect() as db:
            rows = db.execute(
                f"""SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS sessions, SUM({TOTAL_SQL}) AS revenue
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
