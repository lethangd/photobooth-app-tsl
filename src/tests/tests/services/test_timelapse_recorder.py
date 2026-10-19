import io
import time
from pathlib import Path

import cv2
import pytest
from PIL import Image

from photobooth.services.framebooth import recorder as recorder_module
from photobooth.services.framebooth.recorder import MAX_FRAMES, TimelapseRecorder


def _jpeg(color: tuple[int, int, int], size=(320, 180)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="JPEG")
    return buffer.getvalue()


def test_browser_frames_render_a_sped_up_clip_with_a_flash_per_shot(tmp_path: Path):
    rec = TimelapseRecorder()
    rec.start("S1", "browser")
    still = tmp_path / "still.jpg"
    Image.new("RGB", (640, 360), "blue").save(still)
    base = time.monotonic()
    recording = rec.get("S1")
    for i in range(60):  # 15 s of real time at 4 fps
        recording.add(_jpeg((i * 4, 80, 120)), base + i * 0.25)
        if i in (20, 40):
            recording.marks.append((base + i * 0.25, still))
    assert rec.add_frame("S1", _jpeg((0, 0, 0)))  # accepted while recording
    rec.stop("S1")
    assert not rec.add_frame("S1", _jpeg((0, 0, 0)))

    clip = rec.render("S1", "natural", tmp_path)
    video = cv2.VideoCapture(str(clip))
    frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT)) or sum(1 for _ in iter(lambda: video.read()[0], False))
    video.release()
    # at least the minimum length, and the two shots added their flash + hold frames
    assert frames >= recorder_module.MIN_SECONDS * recorder_module.OUTPUT_FPS
    assert clip.suffix == ".mp4" and clip.stat().st_size > 0


def test_frames_are_throttled_and_thinned():
    rec = TimelapseRecorder()
    recording = rec.start("S2", "browser")
    base = time.monotonic()
    recording.add(b"a", base)
    recording.add(b"b", base + 0.01)  # faster than CAPTURE_FPS: ignored
    assert len(recording.frames) == 1
    for i in range(MAX_FRAMES + 5):
        recording.add(b"x", base + 1 + i)
    assert len(recording.frames) <= MAX_FRAMES


def test_server_camera_is_recorded_in_background_and_shots_are_marked():
    rec = TimelapseRecorder()
    jpeg = _jpeg((200, 10, 10))
    rec.set_grab_source(lambda: jpeg)
    rec.start("S3", "server")
    time.sleep(0.8)
    rec.mark_shot(None)
    rec.stop("S3")
    recording = rec.get("S3")
    assert len(recording.frames) >= 2 and len(recording.marks) == 1


def test_new_session_ends_previous_recording():
    rec = TimelapseRecorder()
    rec.start("OLD", "browser")
    rec.start("NEW", "browser")
    assert rec.get("OLD") is None and rec.get("NEW").active


def test_render_without_footage_fails(tmp_path: Path):
    with pytest.raises(ValueError):
        TimelapseRecorder().render("none", "natural", tmp_path)
