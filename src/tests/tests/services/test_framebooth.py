import time
import uuid
from pathlib import Path

from photobooth.services.framebooth import templates
from photobooth.services.framebooth.session_store import SessionStore


def test_discovered_templates_have_matching_slot_count():
    discovered = templates.get_templates()
    assert discovered, "expected at least one bundled frame template to be discovered"

    for template in discovered.values():
        assert len(template.slots) == int(template.frame_type)
        assert template.file.is_file()
        for slot in template.slots:
            assert slot.x >= 0 and slot.y >= 0
            assert slot.x + slot.width <= template.width
            assert slot.y + slot.height <= template.height


def test_invalidate_templates_cache_rescans():
    first = templates.get_templates()
    assert templates.get_templates() is first  # cached, same object

    templates.invalidate_templates_cache()
    assert templates.get_templates() is not first  # fresh dict after invalidation


def test_session_store_capture_roundtrip(tmp_path: Path):
    store = SessionStore(entry_ttl_seconds=0.2, cleanup_interval_seconds=999)
    source = tmp_path / "shot.jpg"
    source.write_bytes(b"\xff\xd8\xff\xd9")

    capture_id, destination = store.add_capture(source)
    assert destination.is_file()
    assert store.get_capture(capture_id) == destination
    assert store.resolve_captures([capture_id]) == [destination]

    # unknown id
    assert store.get_capture(uuid.uuid4()) is None
    assert store.resolve_captures([capture_id, uuid.uuid4()]) is None


def test_session_store_cleanup_drops_expired_files(tmp_path: Path):
    store = SessionStore(entry_ttl_seconds=0.05, cleanup_interval_seconds=999)
    source = tmp_path / "shot.jpg"
    source.write_bytes(b"\xff\xd8\xff\xd9")

    _, destination = store.add_capture(source)
    assert destination.is_file()

    time.sleep(0.1)
    store.cleanup()

    assert not destination.is_file()
    store.clear()
