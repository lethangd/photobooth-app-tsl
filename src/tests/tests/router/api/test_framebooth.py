import io
import logging

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from photobooth.appconfig import appconfig
from photobooth.container import container

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

    correct = appconfig.framebooth.staff_pin
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
