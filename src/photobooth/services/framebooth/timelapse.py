"""Server-side timelapse video fallback.

The kiosk normally records the live-view timelapse in the browser
(MediaRecorder). When that is not available the frontend asks the backend to
build a simple cross-fading slideshow from the still captures with OpenCV.
"""

import logging
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
from PIL import Image, ImageOps

from .filters import apply_filter

logger = logging.getLogger(__name__)

_FPS = 30
_SIZE = (1280, 720)
_HOLD_FRAMES = 13
_TRANSITION_FRAMES = 12


class TimelapseEncoderUnavailableError(RuntimeError):
    """Raised when the OpenCV VideoWriter cannot be opened (VP8 codec missing)."""


def _video_frame_from_capture(capture_path: Path, size: tuple[int, int], filter_id: str) -> np.ndarray:
    with Image.open(capture_path) as image:
        image = ImageOps.exif_transpose(image)
        image = apply_filter(image, filter_id)
        image = ImageOps.fit(image, size, method=Image.Resampling.BICUBIC).convert("RGB")
        rgb = np.asarray(image)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def render_timelapse_video(capture_paths: list[Path], filter_id: str, output_dir: Path) -> Path:
    """Encode a looping cross-fade slideshow. The returned file is named
    ``<uuid>.webm`` so callers can recover the id from ``path.stem``."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{uuid4()}.webm"

    frames = [_video_frame_from_capture(path, _SIZE, filter_id) for path in capture_paths]

    fourcc = cv2.VideoWriter_fourcc(*"VP80")  # pyright: ignore[reportAttributeAccessIssue]
    writer = cv2.VideoWriter(str(output_path), fourcc, _FPS, _SIZE)
    if not writer.isOpened():
        raise TimelapseEncoderUnavailableError("timelapse video encoder is not available")

    try:
        for index, frame in enumerate(frames):
            for _ in range(_HOLD_FRAMES):
                writer.write(frame)

            next_frame = frames[(index + 1) % len(frames)]
            for step in range(_TRANSITION_FRAMES):
                weight = (step + 1) / (_TRANSITION_FRAMES + 1)
                blended = cv2.addWeighted(frame, 1 - weight, next_frame, weight, 0)
                writer.write(blended)
    finally:
        writer.release()

    return output_path
