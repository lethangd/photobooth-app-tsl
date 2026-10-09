"""Auto-discovery of frame templates from ``photobooth/frame/<slot_count>/``.

A frame image is a JPG/PNG/WebP that contains ``slot_count`` solid white (or
solid black) rectangles acting as photo placeholders. The placeholders are
detected with OpenCV connected-components so no manual slot coordinates are
needed - dropping a new frame file into the folder is enough.
"""

import logging
import re
import threading
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .models import FrameSlot, FrameTemplate

logger = logging.getLogger(__name__)

# photobooth/frame/  (this file is photobooth/services/framebooth/templates.py -> parents[2] == photobooth/)
FRAME_DIR = Path(__file__).resolve().parents[2] / "frame"
SUPPORTED_FRAME_TYPES = (2, 3, 4)
_SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}

_cache_lock = threading.Lock()


def _image_to_array(path: Path) -> np.ndarray:
    encoded = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"cannot read frame image {path}")
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def _placeholder_mask(rgb: np.ndarray, placeholder: str) -> np.ndarray:
    if placeholder == "white":
        return (rgb[:, :, 0] > 245) & (rgb[:, :, 1] > 245) & (rgb[:, :, 2] > 245)
    return (rgb[:, :, 0] < 35) & (rgb[:, :, 1] < 35) & (rgb[:, :, 2] < 35)


def _detect_components(rgb: np.ndarray, placeholder: str) -> list[tuple[int, int, int, int, int, float]]:
    height, width = rgb.shape[:2]
    mask = (_placeholder_mask(rgb, placeholder).astype("uint8")) * 255
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    components = []
    frame_area = width * height

    for index in range(1, count):
        x, y, box_width, box_height, area = stats[index]
        box_area = int(box_width * box_height)
        if box_area == 0:
            continue

        fill_ratio = float(area / box_area)
        touches_edge = x <= 1 or y <= 1 or x + box_width >= width - 1 or y + box_height >= height - 1
        if area < frame_area * 0.012:
            continue
        if box_width < width * 0.2 or box_height < height * 0.06:
            continue
        if fill_ratio < 0.45:
            continue
        if touches_edge and area > frame_area * 0.5:
            continue

        components.append((int(x), int(y), int(box_width), int(box_height), int(area), fill_ratio))

    components.sort(key=lambda component: (component[1], component[0]))
    return components


def _detect_slots(path: Path, expected_slots: int) -> tuple[str, list[FrameSlot]]:
    rgb = _image_to_array(path)
    candidates = []
    for placeholder in ("white", "black"):
        components = _detect_components(rgb, placeholder)
        if len(components) == expected_slots:
            score = sum(component[4] for component in components)
            candidates.append((score, placeholder, components))

    if not candidates:
        raise ValueError(f"expected {expected_slots} slots but could not detect them")

    _, placeholder, components = max(candidates, key=lambda item: item[0])
    slots = [FrameSlot(x=x, y=y, width=width, height=height) for x, y, width, height, _, _ in components]
    return placeholder, slots


def _template_id(slot_count: int, path: Path) -> str:
    stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", path.stem).strip("-").lower()
    return f"{slot_count}-{stem or path.stat().st_mtime_ns}"


@lru_cache(maxsize=1)
def _discover_templates() -> dict[str, FrameTemplate]:
    templates: dict[str, FrameTemplate] = {}
    for slot_count in SUPPORTED_FRAME_TYPES:
        folder = FRAME_DIR / str(slot_count)
        if not folder.is_dir():
            continue

        files = sorted(path for path in folder.iterdir() if path.suffix.lower() in _SUPPORTED_SUFFIXES)
        for order, path in enumerate(files, start=1):
            try:
                with Image.open(path) as frame:
                    width, height = frame.size
                placeholder, slots = _detect_slots(path, slot_count)
            except Exception as exc:
                logger.warning("skipping frame %s: %s", path, exc)
                continue

            template = FrameTemplate(
                id=_template_id(slot_count, path),
                frame_type=str(slot_count),
                name=f"Khung {slot_count} anh #{order}",
                file=path,
                width=width,
                height=height,
                placeholder=placeholder,
                slots=slots,
            )
            templates[template.id] = template

    return templates


def get_templates() -> dict[str, FrameTemplate]:
    """Return all discovered templates keyed by id. Result is cached; call
    :func:`invalidate_templates_cache` after adding/removing frame files."""
    with _cache_lock:
        return _discover_templates()


def get_template(template_id: str) -> FrameTemplate | None:
    return get_templates().get(template_id)


def invalidate_templates_cache() -> None:
    """Drop the cached template discovery so the next request rescans the
    frame folders. Called on config reload / after uploading a new frame."""
    with _cache_lock:
        _discover_templates.cache_clear()
    logger.info("framebooth template cache invalidated")


def template_to_public(template: FrameTemplate) -> dict:
    return {
        "id": template.id,
        "frame_type": template.frame_type,
        "name": template.name,
        "width": template.width,
        "height": template.height,
        "slot_count": len(template.slots),
        "preview_url": f"/api/framebooth/templates/{template.id}/preview",
    }


def detect_slots(path: Path, expected_slots: int) -> tuple[str, list[FrameSlot]]:
    """Public wrapper to validate a frame before it is added (raises ValueError if the slots are not found)."""
    return _detect_slots(path, expected_slots)
