"""Timelapse of the whole shooting, recorded from the same single camera that takes the photos.

While the guest poses, the camera already streams its live view to the kiosk screen. The recorder
keeps a few frames per second of that stream (no second camera, the device is never opened twice):

- server camera (Sony a6400 through an HDMI capture card, a webcam, a DSLR via digiCamControl…):
  a background thread reads ``acquisition_service.wait_for_lores_image()``;
- browser camera (laptop webcam used by the kiosk page): the kiosk uploads the frames itself.

Every photo taken during the recording is marked, so the clip shows a white flash and holds the
real photo for a moment at that instant. ``render()`` speeds everything up into a ~12 s clip,
encoded as H.264 MP4 (fast, and plays on every phone including iPhones), VP8 WebM as a fallback.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
from PIL import Image, ImageOps

from .filters import apply_filter
from .letterbox import content_box

logger = logging.getLogger(__name__)

CAPTURE_FPS = 4  # frames kept per second of real time
MAX_FRAMES = 720  # ~3 min at 4 fps; older frames get thinned out beyond that
OUTPUT_FPS = 30
MIN_SECONDS, MAX_SECONDS = 6.0, 14.0
FLASH_FRAMES = 5
STILL_HOLD_FRAMES = 14
MAX_WIDTH = 1280
IDLE_STOP_SECONDS = 15 * 60  # safety net when a kiosk never says "stop"


class TimelapseEncoderUnavailableError(RuntimeError):
    """Raised when the OpenCV VideoWriter cannot be opened (VP8 codec missing)."""


@dataclass
class Recording:
    session_id: str
    source: str  # "server" | "browser"
    frames: list[tuple[float, bytes]] = field(default_factory=list)
    marks: list[tuple[float, Path | None]] = field(default_factory=list)
    active: bool = False
    started_at: float = field(default_factory=time.monotonic)
    last_frame_at: float = 0.0

    def add(self, jpeg: bytes, at: float | None = None) -> None:
        now = at if at is not None else time.monotonic()
        if now - self.last_frame_at < 1 / (CAPTURE_FPS + 0.5):
            return
        self.frames.append((now, jpeg))
        self.last_frame_at = now
        if len(self.frames) > MAX_FRAMES:
            # keep the whole story: drop every other frame instead of the oldest ones
            self.frames = self.frames[::2]


class TimelapseRecorder:
    def __init__(self) -> None:
        self._recordings: dict[str, Recording] = {}
        self._lock = threading.Lock()
        self._grab_source = None  # callable returning one JPEG frame of the server camera

    def set_grab_source(self, grab) -> None:
        self._grab_source = grab

    # ───── control ─────

    def start(self, session_id: str, source: str) -> Recording:
        """Start (or resume, e.g. for a retake) the recording of a session."""
        with self._lock:
            self._drop_other_sessions(session_id)
            recording = self._recordings.get(session_id)
            if recording is None:
                recording = self._recordings[session_id] = Recording(session_id, source)
            recording.source = source
            if recording.active:
                return recording
            recording.active = True
            recording.started_at = time.monotonic()
        if source == "server":
            threading.Thread(target=self._grab_loop, args=(recording,), name=f"timelapse-{session_id}", daemon=True).start()
        logger.info(f"timelapse recording started for {session_id} ({source} camera)")
        return recording

    def stop(self, session_id: str) -> Recording | None:
        with self._lock:
            recording = self._recordings.get(session_id)
            if recording:
                recording.active = False
        if recording:
            logger.info(f"timelapse recording stopped for {session_id}: {len(recording.frames)} frame(s), {len(recording.marks)} shot(s)")
        return recording

    def add_frame(self, session_id: str, jpeg: bytes) -> bool:
        with self._lock:
            recording = self._recordings.get(session_id)
            if not recording or not recording.active:
                return False
            recording.add(jpeg)
        return True

    def mark_shot(self, still: Path | None) -> None:
        """A photo was just taken: every recording in progress gets a flash + the photo at this instant."""
        now = time.monotonic()
        with self._lock:
            for recording in self._recordings.values():
                if recording.active:
                    recording.marks.append((now, still))

    def get(self, session_id: str) -> Recording | None:
        with self._lock:
            return self._recordings.get(session_id)

    def has_footage(self, session_id: str | None) -> bool:
        recording = self.get(session_id) if session_id else None
        return bool(recording and len(recording.frames) >= 8)

    def discard(self, session_id: str) -> None:
        with self._lock:
            self._recordings.pop(session_id, None)

    def _drop_other_sessions(self, keep: str) -> None:
        # one kiosk, one guest at a time: a new session ends the previous recordings
        for session_id in [s for s in self._recordings if s != keep]:
            self._recordings[session_id].active = False
            del self._recordings[session_id]

    def _grab_loop(self, recording: Recording) -> None:
        grab = self._grab_source
        if grab is None:
            logger.warning("timelapse: no server camera to record from")
            return
        while recording.active and time.monotonic() - recording.started_at < IDLE_STOP_SECONDS:
            started = time.monotonic()
            try:
                recording.add(grab(), started)
            except Exception:
                # the live view pauses while a still is taken (DSLR) or the camera restarts: just retry
                time.sleep(0.25)
                continue
            time.sleep(max(0.0, 1 / CAPTURE_FPS - (time.monotonic() - started)))
        recording.active = False

    # ───── encoding ─────

    def render(self, session_id: str, filter_id: str, output_dir: Path) -> Path:
        """Encode the recording into a sped-up clip (``<uuid>.mp4``); flash + photo at every shot."""
        recording = self.get(session_id)
        if not recording or len(recording.frames) < 2:
            raise ValueError("no footage recorded for this session")
        frames = list(recording.frames)
        marks = sorted(recording.marks, key=lambda mark: mark[0])

        first = _decode(frames[0][1])
        # black bars of the camera signal (same for the whole recording): measured on a frame from the middle
        bars = content_box(cv2.cvtColor(_decode(frames[len(frames) // 2][1]), cv2.COLOR_BGR2RGB))
        if bars:
            left, top, right, bottom = bars
            first = first[top:bottom, left:right]
        size = _output_size(first.shape[1], first.shape[0])
        t0, t1 = frames[0][0], frames[-1][0]
        span = max(t1 - t0, 0.001)
        extra = len(marks) * (FLASH_FRAMES + STILL_HOLD_FRAMES)
        duration = min(MAX_SECONDS, max(MIN_SECONDS, span / 8))
        count = max(2, int(duration * OUTPUT_FPS) - extra)

        output_dir.mkdir(parents=True, exist_ok=True)
        writer = _open_writer(output_dir, size)
        output_path = writer.path

        cache: dict[int, np.ndarray] = {}

        def frame_at(index: int) -> np.ndarray:
            if index not in cache:
                cache.clear()  # frames are visited in order: keep memory flat
                image = _decode(frames[index][1])
                if bars:
                    image = image[bars[1] : bars[3], bars[0] : bars[2]]
                cache[index] = _prepare(image, size, filter_id)
            return cache[index]

        try:
            source_index = 0
            mark_index = 0
            last = frame_at(0)
            for step in range(count):
                at = t0 + span * step / max(1, count - 1)
                while source_index + 1 < len(frames) and frames[source_index + 1][0] <= at:
                    source_index += 1
                last = frame_at(source_index)
                writer.write(last)
                while mark_index < len(marks) and marks[mark_index][0] <= at:
                    _write_shot(writer, last, marks[mark_index][1], size, filter_id)
                    mark_index += 1
            for _, still in marks[mark_index:]:
                _write_shot(writer, last, still, size, filter_id)
        finally:
            writer.release()
        logger.info(f"timelapse rendered for {session_id}: {output_path.name} ({count + extra} frames)")
        return output_path


class _Mp4Writer:
    """H.264 through PyAV (bundled libx264): ~1 s for a 12 s clip instead of ~20 s with VP8."""

    def __init__(self, path: Path, size: tuple[int, int]):
        import av  # noqa: PLC0415

        self.path = path
        self._container = av.open(str(path), "w", format="mp4")
        self._stream = self._container.add_stream("libx264", rate=OUTPUT_FPS)
        self._stream.width, self._stream.height = size
        self._stream.pix_fmt = "yuv420p"
        # faststart: the phone starts playing before the whole file is downloaded
        self._stream.options = {"preset": "veryfast", "crf": "22", "movflags": "+faststart"}
        self._frame_type = av.VideoFrame

    def write(self, frame: np.ndarray) -> None:
        for packet in self._stream.encode(self._frame_type.from_ndarray(frame, format="bgr24")):
            self._container.mux(packet)

    def release(self) -> None:
        for packet in self._stream.encode():
            self._container.mux(packet)
        self._container.close()


class _WebmWriter:
    def __init__(self, path: Path, size: tuple[int, int]):
        self.path = path
        self._writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"VP80"), OUTPUT_FPS, size)  # pyright: ignore[reportAttributeAccessIssue]
        if not self._writer.isOpened():
            raise TimelapseEncoderUnavailableError("timelapse video encoder is not available")

    def write(self, frame: np.ndarray) -> None:
        self._writer.write(frame)

    def release(self) -> None:
        self._writer.release()


def _open_writer(output_dir: Path, size: tuple[int, int]):
    try:
        return _Mp4Writer(output_dir / f"{uuid4()}.mp4", size)
    except Exception as exc:
        logger.warning(f"H.264 encoder unavailable ({exc}), falling back to VP8 WebM")
        return _WebmWriter(output_dir / f"{uuid4()}.webm", size)


def _decode(jpeg: bytes) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("unreadable frame")
    return image


def _output_size(width: int, height: int) -> tuple[int, int]:
    scale = min(1.0, MAX_WIDTH / max(width, height))
    # even dimensions for the encoder
    return int(width * scale) // 2 * 2, int(height * scale) // 2 * 2


def _prepare(image: np.ndarray, size: tuple[int, int], filter_id: str) -> np.ndarray:
    if (image.shape[1], image.shape[0]) != size:
        image = _cover(image, size)
    if filter_id and filter_id != "natural":
        rgb = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        image = cv2.cvtColor(np.asarray(apply_filter(rgb, filter_id).convert("RGB")), cv2.COLOR_RGB2BGR)
    return image


def _cover(image: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    width, height = size
    scale = max(width / image.shape[1], height / image.shape[0])
    resized = cv2.resize(image, (max(width, round(image.shape[1] * scale)), max(height, round(image.shape[0] * scale))), interpolation=cv2.INTER_AREA)
    top = (resized.shape[0] - height) // 2
    left = (resized.shape[1] - width) // 2
    return resized[top : top + height, left : left + width]


def _still_frame(still: Path | None, size: tuple[int, int], filter_id: str) -> np.ndarray | None:
    if not still or not still.is_file():
        return None
    try:
        with Image.open(still) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            if filter_id and filter_id != "natural":
                image = apply_filter(image, filter_id).convert("RGB")
            fitted = ImageOps.fit(image, size, method=Image.Resampling.BICUBIC)
            return cv2.cvtColor(np.asarray(fitted), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        logger.warning(f"timelapse: cannot use still {still}: {exc}")
        return None


def _write_shot(writer, live: np.ndarray, still: Path | None, size: tuple[int, int], filter_id: str) -> None:
    """White flash, then the real photo frozen for a moment, like the kiosk screen does."""
    photo = _still_frame(still, size, filter_id)
    shown = photo if photo is not None else live
    white = np.full_like(shown, 255)
    for step in range(FLASH_FRAMES):
        weight = 1 - step / FLASH_FRAMES
        writer.write(cv2.addWeighted(white, weight, shown, 1 - weight, 0))
    for _ in range(STILL_HOLD_FRAMES):
        writer.write(shown)


recorder = TimelapseRecorder()
