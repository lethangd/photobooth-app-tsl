import io
from datetime import date

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from photobooth.appconfig import appconfig
from photobooth.services import credentials
from photobooth.services.framebooth import templates
from photobooth.services.framebooth.ledger import KioskLedger


def test_kiosk_admin_requires_login(client: TestClient):
    client.headers = {}
    assert client.get("/admin/kiosk/stats").status_code == 401


def test_kiosk_pin_payment_shows_up_in_stats(client_authenticated: TestClient, tmp_path, monkeypatch):
    from photobooth.routers.api import framebooth as framebooth_router
    from photobooth.routers.api_admin import kiosk as kiosk_router

    isolated = KioskLedger(tmp_path / "ledger.sqlite")
    monkeypatch.setattr(framebooth_router, "ledger", isolated)
    monkeypatch.setattr(kiosk_router, "ledger", isolated)
    framebooth_router._pin_failures = 0
    framebooth_router._pin_locked_until = 0.0

    price = next(tier.price for tier in appconfig.framebooth.pricing if tier.slot_count == 3)
    pin = credentials.DEFAULT_STAFF_PIN
    body = {"pin": pin, "session_id": "PBTEST", "purpose": "package", "slot_count": 3}
    assert client_authenticated.post("/framebooth/verify-pin", json=body).json()["ok"] is True
    retake = {"pin": pin, "session_id": "PBTEST", "purpose": "retake", "retake_shots": 2}
    assert client_authenticated.post("/framebooth/verify-pin", json=retake).json()["ok"] is True

    stats = client_authenticated.get("/admin/kiosk/stats", params={"day": date.today().isoformat()}).json()
    assert stats["sessions"] == 1
    assert stats["revenue"] == price + 2 * appconfig.framebooth.retake_price
    assert len(stats["series"]) == 7

    sessions = client_authenticated.get("/admin/kiosk/sessions").json()
    assert sessions[0]["session_id"] == "PBTEST" and sessions[0]["retake_shots"] == 2
    events = client_authenticated.get("/admin/kiosk/pin-events").json()
    assert [event["purpose"] for event in events] == ["retake", "package"]


def test_kiosk_printer_status(client_authenticated: TestClient):
    response = client_authenticated.get("/admin/kiosk/printer")
    assert response.status_code == 200
    body = response.json()
    assert {"configured_name", "default_name", "kiosk_printer", "printers"} <= body.keys()


def _frame_png(slots: int) -> bytes:
    image = Image.new("RGB", (600, 400 * slots), "#2b3bff")
    draw = ImageDraw.Draw(image)
    for index in range(slots):
        draw.rectangle([60, 40 + index * 400, 540, 360 + index * 400], fill="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_kiosk_frames_upload_list_delete(client_authenticated: TestClient, tmp_path, monkeypatch):
    monkeypatch.setattr(templates, "FRAME_DIR", tmp_path / "frame")
    templates.invalidate_templates_cache()
    try:
        bad = client_authenticated.post("/admin/kiosk/frames", data={"slot_count": "3"}, files={"file": ("bad.png", _frame_png(2), "image/png")})
        assert bad.status_code == 422

        ok = client_authenticated.post("/admin/kiosk/frames", data={"slot_count": "2"}, files={"file": ("my frame.png", _frame_png(2), "image/png")})
        assert ok.status_code == 201, ok.text
        assert len(ok.json()["slots"]) == 2

        frames = client_authenticated.get("/admin/kiosk/frames").json()
        assert [frame["file_name"] for frame in frames] == ["my-frame.png"]

        assert client_authenticated.delete(f"/admin/kiosk/frames/{frames[0]['id']}").status_code == 204
        assert client_authenticated.get("/admin/kiosk/frames").json() == []
    finally:
        templates.invalidate_templates_cache()


def test_kiosk_overview_csv_detail_and_multicam(client_authenticated: TestClient, tmp_path, monkeypatch):
    from photobooth.routers.api_admin import kiosk as kiosk_router

    isolated = KioskLedger(tmp_path / "ledger.sqlite")
    monkeypatch.setattr(kiosk_router, "ledger", isolated)
    isolated.record_pin("PBCSV1", "package", 70000, ok=True)
    isolated.record_package_paid("PBCSV1", 3, 70000)

    overview = client_authenticated.get("/admin/kiosk/overview").json()
    assert {"camera", "printer", "cloud"} <= overview.keys()

    csv = client_authenticated.get("/admin/kiosk/sessions.csv")
    assert csv.status_code == 200
    assert csv.content.startswith("\ufeff".encode())
    assert "PBCSV1" in csv.content.decode("utf-8")

    detail = client_authenticated.get("/admin/kiosk/sessions/PBCSV1").json()
    assert detail["total"] == 70000 and len(detail["pin_events"]) == 1 and detail["media_url"] is None
    assert client_authenticated.get("/admin/kiosk/sessions/NOPE").status_code == 404
    assert client_authenticated.post("/admin/kiosk/sessions/PBCSV1/print").status_code == 404

    stats = client_authenticated.get("/admin/kiosk/stats", params={"range_days": 7}).json()
    assert stats["revenue"] == 70000 and "previous" in stats

    assert client_authenticated.post("/admin/kiosk/printer/select", json={"name": "no such printer"}).status_code == 404
    multicam = client_authenticated.get("/admin/kiosk/multicam").json()
    assert {"configured", "nodes", "calibrated"} <= multicam.keys()


def test_security_change_admin_password_and_pin(client_authenticated: TestClient):
    status_ = client_authenticated.get("/admin/kiosk/security").json()
    assert status_["admin_password_default"] and status_["staff_pin_default"]

    wrong = client_authenticated.post("/admin/kiosk/security/staff-pin", json={"current_password": "nope", "new_value": "4321"})
    assert wrong.status_code == 403
    invalid = client_authenticated.post("/admin/kiosk/security/staff-pin", json={"current_password": "0000", "new_value": "12a4"})
    assert invalid.status_code == 422

    assert client_authenticated.post("/admin/kiosk/security/staff-pin", json={"current_password": "0000", "new_value": "4321"}).status_code == 200
    assert (
        client_authenticated.post("/admin/kiosk/security/admin-password", json={"current_password": "0000", "new_value": "secret-42"}).status_code
        == 200
    )

    stored = credentials.secrets_file().read_text(encoding="utf-8")
    assert "4321" not in stored and "secret-42" not in stored  # only hashes land in .env
    assert credentials.verify_staff_pin("4321") and not credentials.verify_staff_pin(credentials.DEFAULT_STAFF_PIN)
    assert credentials.verify_admin_password("secret-42") and not credentials.verify_admin_password("0000")
    assert not client_authenticated.get("/admin/kiosk/security").json()["admin_password_default"]
