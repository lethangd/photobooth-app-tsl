import io
import logging
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from photobooth.appconfig import appconfig
from photobooth.container import container
from photobooth.services import credentials

logger = logging.getLogger(name=None)


def _capture(client: TestClient) -> str:
    response = client.post("/framebooth/capture")
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _pick_template(client: TestClient, slot_count: int) -> dict:
    config = client.get("/framebooth/config").json()
    for frame_type in config["frame_types"]:
        if frame_type["slot_count"] == slot_count and frame_type["templates"]:
            return frame_type["templates"][0]
    pytest.skip(f"no frame template with {slot_count} slots available")


def test_framebooth_config_shape(client: TestClient):
    response = client.get("/framebooth/config")
    assert response.status_code == 200
    body = response.json()

    # timings are sourced from appconfig.framebooth and must all be present for the kiosk JS
    for key in (
        "package_select_timeout_seconds",
        "shot_buffer_count",
        "countdown_seconds",
        "get_ready_seconds",
        "photo_select_warn_seconds",
        "photo_select_grace_seconds",
        "filter_select_warn_seconds",
        "filter_select_grace_seconds",
        "final_preview_timeout_seconds",
        "digital_delivery_default_enabled",
        "filters",
        "frame_types",
    ):
        assert key in body, f"missing {key} in framebooth config"

    assert body["shot_buffer_count"] == appconfig.framebooth.shot_buffer_count
    assert {f["id"] for f in body["filters"]} == {f.id for f in appconfig.framebooth.filters}

    pricing = {tier.slot_count: tier.price for tier in appconfig.framebooth.pricing}
    for frame_type in body["frame_types"]:
        assert frame_type["shots_to_take"] == frame_type["slot_count"] + body["shot_buffer_count"]
        assert frame_type["price"] == pricing.get(frame_type["slot_count"], 0)


def test_framebooth_config_reflects_admin_change(client: TestClient):
    original = appconfig.framebooth.shot_buffer_count
    try:
        appconfig.framebooth.shot_buffer_count = 3
        body = client.get("/framebooth/config").json()
        assert body["shot_buffer_count"] == 3
        assert all(ft["shots_to_take"] == ft["slot_count"] + 3 for ft in body["frame_types"])
    finally:
        appconfig.framebooth.shot_buffer_count = original


def test_framebooth_capture_roundtrip(client: TestClient):
    capture_id = _capture(client)

    response = client.get(f"/framebooth/captures/{capture_id}")
    assert response.status_code == 200
    with Image.open(io.BytesIO(response.content)) as img:
        img.verify()


def test_framebooth_capture_unknown(client: TestClient):
    response = client.get("/framebooth/captures/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_framebooth_composite_preview(client: TestClient):
    template = _pick_template(client, slot_count=2)
    capture_ids = [_capture(client) for _ in range(2)]

    response = client.post(
        f"/framebooth/templates/{template['id']}/composite-preview",
        json={"capture_ids": capture_ids, "filter_id": "mono"},
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "image/jpeg"
    with Image.open(io.BytesIO(response.content)) as img:
        img.verify()


def test_framebooth_composite_preview_wrong_capture_count(client: TestClient):
    template = _pick_template(client, slot_count=2)
    response = client.post(
        f"/framebooth/templates/{template['id']}/composite-preview",
        json={"capture_ids": [_capture(client)], "filter_id": "natural"},
    )
    assert response.status_code == 400


def test_framebooth_unknown_template(client: TestClient):
    response = client.post(
        "/framebooth/templates/does-not-exist/composite-preview",
        json={"capture_ids": [_capture(client)], "filter_id": "natural"},
    )
    assert response.status_code == 404


def test_framebooth_render_creates_gallery_item(client: TestClient):
    template = _pick_template(client, slot_count=2)
    capture_ids = [_capture(client) for _ in range(2)]
    before = container.mediacollection_service.count()

    response = client.post(
        "/framebooth/render",
        json={
            "template_id": template["id"],
            "capture_ids": capture_ids,
            "all_capture_ids": capture_ids,
            "filter_id": "film",
            "session_id": "PBTEST1",
            "digital_delivery": True,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["media_url"] == f"/media/full/{body['id']}"
    assert body["retention_days"] == appconfig.framebooth.digital_delivery_retention_days
    assert container.mediacollection_service.count() == before + 1

    from uuid import UUID

    item = container.mediacollection_service.get_item(UUID(body["id"]))
    assert item.media_type == "collage"
    assert item.show_in_gallery is True
    assert item.pipeline_config["framebooth"] is True
    assert item.pipeline_config["template_id"] == template["id"]


def test_framebooth_render_unknown_filter(client: TestClient):
    template = _pick_template(client, slot_count=2)
    response = client.post(
        "/framebooth/render",
        json={
            "template_id": template["id"],
            "capture_ids": [_capture(client), _capture(client)],
            "filter_id": "no-such-filter",
        },
    )
    assert response.status_code == 400


def test_framebooth_verify_pin(client: TestClient):
    from photobooth.routers.api import framebooth as framebooth_router

    correct = credentials.DEFAULT_STAFF_PIN
    wrong = "0000" if correct != "0000" else "1111"

    assert client.post("/framebooth/verify-pin", json={"pin": correct}).json() == {"ok": True, "locked_seconds": 0}
    assert client.post("/framebooth/verify-pin", json={"pin": wrong}).json()["ok"] is False

    # too many wrong tries lock the PIN pad, even the correct PIN is refused while locked
    for _ in range(framebooth_router._PIN_MAX_FAILURES):
        response = client.post("/framebooth/verify-pin", json={"pin": wrong}).json()
    assert response["ok"] is False and response["locked_seconds"] > 0
    assert client.post("/framebooth/verify-pin", json={"pin": correct}).json()["ok"] is False

    framebooth_router._pin_locked_until = 0.0
    framebooth_router._pin_failures = 0
    assert client.post("/framebooth/verify-pin", json={"pin": correct}).json()["ok"] is True


def test_framebooth_camera_status(client: TestClient):
    response = client.get("/framebooth/camera-status")
    assert response.status_code == 200
    assert isinstance(response.json()["available"], bool)
    assert response.json()["virtual"] is True  # the test config runs the demo VirtualCamera


def test_framebooth_upload_browser_capture(client: TestClient):
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), "red").save(buffer, format="JPEG")

    response = client.post("/framebooth/captures/upload", content=buffer.getvalue(), headers={"Content-Type": "image/jpeg"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert client.get(body["preview_url"].removeprefix("/api")).status_code == 200

    assert client.post("/framebooth/captures/upload", content=b"not an image").status_code == 400
    assert client.post("/framebooth/captures/upload", content=b"").status_code == 400


def test_framebooth_payment_confirmed_by_pin(client: TestClient):
    from photobooth.routers.api import framebooth as framebooth_router

    framebooth_router._pin_failures = 0
    framebooth_router._pin_locked_until = 0.0
    created = client.post("/framebooth/payments", json={"session_id": "PBPAY1", "purpose": "package", "quantity": 3})
    assert created.status_code == 200, created.text
    payment = created.json()
    price = next(tier.price for tier in appconfig.framebooth.pricing if tier.slot_count == 3)
    assert payment["amount"] == price and payment["status"] == "pending" and payment["reference"] == "TSLPBPAY1"

    ok = client.post(
        "/framebooth/verify-pin",
        json={"pin": credentials.DEFAULT_STAFF_PIN, "session_id": "PBPAY1", "purpose": "package", "slot_count": 3, "reference": payment["reference"]},
    ).json()
    assert ok["ok"]
    after = client.get(f"/framebooth/payments/{payment['reference']}").json()
    assert after["status"] == "paid" and after["method"] == "pin"


def test_framebooth_payment_rejects_unknown_package_and_voucher(client: TestClient):
    assert client.post("/framebooth/payments", json={"session_id": "PBX", "purpose": "package", "quantity": 7}).status_code == 422
    bad = client.post("/framebooth/payments", json={"session_id": "PBX", "purpose": "package", "quantity": 2, "voucher_code": "NOPE"})
    assert bad.status_code == 422 and "Mã" in bad.json()["detail"]
    assert client.post("/framebooth/vouchers/check", json={"code": "NOPE", "slot_count": 2}).json()["ok"] is False


def test_framebooth_sepay_webhook_requires_key(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    body = {"id": uuid4().hex, "transferType": "in", "transferAmount": 10000, "content": "TSLPBNONE"}
    monkeypatch.delenv("SEPAY_WEBHOOK_KEY", raising=False)
    assert client.post("/framebooth/payments/sepay-webhook", json=body).status_code == 401

    monkeypatch.setenv("SEPAY_WEBHOOK_KEY", "k1")
    created = client.post("/framebooth/payments", json={"session_id": "PBHOOK", "purpose": "retake", "quantity": 1}).json()
    body["content"] = f"chuyen tien {created['reference']}"
    body["transferAmount"] = created["amount"]
    assert client.post("/framebooth/payments/sepay-webhook", json=body, headers={"Authorization": "Apikey wrong"}).status_code == 401
    assert client.post("/framebooth/payments/sepay-webhook", json=body, headers={"Authorization": "Apikey k1"}).json() == {"success": True}
    assert client.get(f"/framebooth/payments/{created['reference']}").json()["status"] == "paid"


def test_framebooth_loyalty_and_feedback(client: TestClient):
    assert client.post("/framebooth/loyalty", json={"session_id": "PBLOY", "phone": "123"}).status_code == 422
    stamp = client.post("/framebooth/loyalty", json={"session_id": "PBLOY", "phone": "0912 000 111"}).json()
    assert stamp["target"] == appconfig.framebooth.loyalty_stamps_for_reward and stamp["stamps"] >= 1
    assert client.post("/framebooth/feedback", json={"session_id": "PBLOY", "rating": 3, "share_consent": True}).status_code == 200
    assert client.post("/framebooth/feedback", json={"session_id": "PBLOY", "rating": 9}).status_code == 422


def test_framebooth_render_with_overlay_and_print_disabled(client: TestClient):
    import base64

    template = _pick_template(client, slot_count=2)
    capture_ids = [_capture(client) for _ in range(2)]
    overlay = io.BytesIO()
    Image.new("RGBA", (40, 60), (43, 59, 255, 128)).save(overlay, format="PNG")
    response = client.post(
        "/framebooth/render",
        json={
            "template_id": template["id"],
            "capture_ids": capture_ids,
            "filter_id": "natural",
            "session_id": "PBOVL",
            "digital_delivery": False,
            "copies": 2,
            "overlay_png": "data:image/png;base64," + base64.b64encode(overlay.getvalue()).decode(),
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["print"] == {"ok": True, "simulated": True}
