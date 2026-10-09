from datetime import date, timedelta

from photobooth.services.framebooth.ledger import KioskLedger


def test_ledger_day_stats_and_history(tmp_path):
    ledger = KioskLedger(tmp_path / "ledger.sqlite")

    ledger.record_pin("PB1", "package", 70000, ok=False)
    ledger.record_pin("PB1", "package", 70000, ok=True)
    ledger.record_package_paid("PB1", 3, 70000)
    ledger.record_pin("PB1", "retake", 20000, ok=True)
    ledger.record_retake_paid("PB1", 2, 20000)
    ledger.record_print("PB1", "media-1", digital=True, cloud_url="https://example/x")

    ledger.record_package_paid("PB2", 2, 50000)

    today = date.today()
    stats = ledger.day_stats(today)
    assert stats["sessions"] == 2
    assert stats["revenue"] == 140000
    assert stats["retake_revenue"] == 20000
    assert stats["printed"] == 1
    assert stats["pin_ok"] == 2 and stats["pin_failed"] == 1
    assert {row["slot_count"]: row["sessions"] for row in stats["by_package"]} == {2: 1, 3: 1}

    sessions = {row["session_id"]: row for row in ledger.sessions(today)}
    assert sessions["PB1"]["total"] == 90000 and sessions["PB1"]["retake_shots"] == 2
    assert sessions["PB1"]["digital"] is True and sessions["PB2"]["printed_at"] is None

    assert [event["ok"] for event in ledger.pin_events(today)] == [True, True, False]

    series = ledger.daily_series(7, today)
    assert len(series) == 7 and series[-1] == {"day": today.isoformat(), "sessions": 2, "revenue": 140000}
    assert ledger.day_stats(today - timedelta(days=1))["sessions"] == 0


def test_ledger_retake_without_known_session(tmp_path):
    ledger = KioskLedger(tmp_path / "ledger.sqlite")
    ledger.record_retake_paid("PB9", 1, 10000)
    assert ledger.day_stats(date.today())["revenue"] == 10000
