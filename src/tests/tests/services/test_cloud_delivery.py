from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from photobooth.appconfig import appconfig
from photobooth.services.framebooth.cloud import CloudDeliveryService, R2Settings


def _service_with_fake_client(objects: list[dict]) -> tuple[CloudDeliveryService, MagicMock]:
    client = MagicMock()
    client.get_paginator.return_value.paginate.return_value = [{"Contents": objects}]
    service = CloudDeliveryService()
    service._client = client
    service._settings = R2Settings("https://x", "bucket", "https://pub", "ak", "sk")
    return service, client


def test_sweep_deletes_only_expired_sessions():
    now = datetime.now(UTC)
    retention = appconfig.framebooth.digital_delivery_retention_days
    service, client = _service_with_fake_client(
        [
            {"Key": "sessions/old/index.html", "LastModified": now - timedelta(days=retention + 1)},
            {"Key": "sessions/old/collage.jpg", "LastModified": now - timedelta(days=retention + 1)},
            {"Key": "sessions/new/index.html", "LastModified": now - timedelta(hours=1)},
        ]
    )

    assert service.sweep_expired() == 2

    deleted = client.delete_objects.call_args.kwargs["Delete"]["Objects"]
    assert deleted == [{"Key": "sessions/old/index.html"}, {"Key": "sessions/old/collage.jpg"}]


def test_sweep_without_expired_does_not_call_delete():
    service, client = _service_with_fake_client([{"Key": "sessions/new/a.jpg", "LastModified": datetime.now(UTC)}])

    assert service.sweep_expired() == 0
    client.delete_objects.assert_not_called()


def test_sweep_survives_network_errors():
    service, client = _service_with_fake_client([])
    client.get_paginator.side_effect = RuntimeError("offline")

    assert service.sweep_expired() == 0


def test_sweep_is_noop_when_not_configured():
    assert CloudDeliveryService().sweep_expired() == 0


def test_delivery_page_and_boomerang(tmp_path):
    from PIL import Image

    from photobooth.services.framebooth.cloud import make_boomerang, render_delivery_page

    sources = []
    for index, color in enumerate(["red", "green", "blue"]):
        path = tmp_path / f"{index}.jpg"
        Image.new("RGB", (300, 200), color).save(path)
        sources.append(path)
    gif = make_boomerang(sources, tmp_path / "b.gif")
    assert gif and Image.open(gif).n_frames == 4  # forth and back without repeating the ends

    page = render_delivery_page({"session": "PB1", "collage": "collage.jpg", "originals": [], "note": "</script><b>"})
    assert "__SESSION_DATA__" not in page and '"session": "PB1"' in page and "</script><b>" not in page
