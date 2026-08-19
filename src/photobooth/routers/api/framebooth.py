import logging
import re
import shutil
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from PIL import Image, ImageEnhance, ImageOps
from pydantic import BaseModel, Field

from ... import PATH_PROCESSED, TMP_PATH
from ...container import container
from ...database.models import Mediaitem
from ...utils.helper import filename_str_time

router = APIRouter(prefix="/framebooth", tags=["framebooth"])
logger = logging.getLogger(__name__)

FRAME_DIR = Path(__file__).resolve().parents[2] / "frame"
CAPTURE_DIR = Path(TMP_PATH) / "framebooth"
TIMELAPSE_DIR = CAPTURE_DIR / "timelapse"
SUPPORTED_FRAME_TYPES = (2, 3, 4)

SHOT_BUFFER_COUNT = 2
CAPTURE_COUNTDOWN_SECONDS = 10
GET_READY_DURATION_SECONDS = 3
PAYMENT_MOCK_SECONDS = 2
PRINTING_MOCK_SECONDS = 3
QR_DOWNLOAD_SECONDS = 8
THANK_YOU_SECONDS = 5
DIGITAL_DELIVERY_RETENTION_DAYS = 7
TIMELAPSE_RENDER_MOCK_SECONDS = 6
PRICING = {2: 50_000, 3: 70_000, 4: 90_000}


class FrameSlot(BaseModel):
    x: int
    y: int
    width: int
    height: int


class FrameTemplate(BaseModel):
    id: str
    frame_type: str
    name: str
    file: Path
    width: int
    height: int
    placeholder: str
    slots: list[FrameSlot]


class RenderRequest(BaseModel):
    template_id: str
    capture_ids: list[UUID] = Field(min_length=1)
    all_capture_ids: list[UUID] = Field(default_factory=list)
    filter_id: str = "natural"
    session_id: str | None = None
    digital_delivery: bool = True


class PreviewRequest(BaseModel):
    capture_ids: list[UUID] = Field(min_length=1)
    filter_id: str = "natural"


class TimelapseRequest(BaseModel):
    capture_ids: list[UUID] = Field(min_length=2)
    filter_id: str = "natural"
    session_id: str | None = None


CAPTURES: dict[UUID, Path] = {}
TIMELAPSES: dict[UUID, Path] = {}

FILTERS = [
    {"id": "natural", "name": "Natural", "css_filter": "none"},
    {"id": "vivid", "name": "Vivid", "css_filter": "saturate(1.35) contrast(1.1)"},
    {"id": "warm", "name": "Warm", "css_filter": "sepia(.16) saturate(1.2) brightness(1.04)"},
    {"id": "mono", "name": "B&W", "css_filter": "grayscale(1) contrast(1.08)"},
    {"id": "film", "name": "Film", "css_filter": "sepia(.24) contrast(1.08) saturate(.92)"},
]


def _template_to_public(template: FrameTemplate) -> dict:
    return {
        "id": template.id,
        "frame_type": template.frame_type,
        "name": template.name,
        "width": template.width,
        "height": template.height,
        "slot_count": len(template.slots),
        "preview_url": f"/api/framebooth/templates/{template.id}/preview",
    }


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
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
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
def _get_templates() -> dict[str, FrameTemplate]:
    templates: dict[str, FrameTemplate] = {}
    for slot_count in SUPPORTED_FRAME_TYPES:
        folder = FRAME_DIR / str(slot_count)
        if not folder.is_dir():
            continue

        files = sorted(path for path in folder.iterdir() if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
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


def _filter_to_public(filter_config: dict) -> dict:
    return {
        "id": filter_config["id"],
        "name": filter_config["name"],
        "css_filter": filter_config["css_filter"],
    }


def _apply_filter(image: Image.Image, filter_id: str) -> Image.Image:
    image = image.convert("RGB")
    if filter_id == "vivid":
        image = ImageEnhance.Color(image).enhance(1.35)
        return ImageEnhance.Contrast(image).enhance(1.1)
    if filter_id == "warm":
        r, g, b = image.split()
        r = r.point(lambda value: min(255, int(value * 1.06 + 4)))
        b = b.point(lambda value: max(0, int(value * 0.93)))
        image = Image.merge("RGB", (r, g, b))
        return ImageEnhance.Color(image).enhance(1.12)
    if filter_id == "mono":
        return ImageOps.grayscale(image).convert("RGB")
    if filter_id == "film":
        r, g, b = image.split()
        r = r.point(lambda value: min(255, int(value * 1.05 + 3)))
        g = g.point(lambda value: min(255, int(value * 1.02)))
        b = b.point(lambda value: max(0, int(value * 0.9)))
        image = Image.merge("RGB", (r, g, b))
        image = ImageEnhance.Contrast(image).enhance(1.08)
        return ImageEnhance.Color(image).enhance(0.92)
    return image


def _validate_render_request(request: RenderRequest) -> tuple[FrameTemplate, list[Path]]:
    templates = _get_templates()
    template = templates.get(request.template_id)
    if not template:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "frame template not found")

    if request.filter_id not in {filter_config["id"] for filter_config in FILTERS}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "filter not found")

    if len(request.capture_ids) != len(template.slots):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"template requires {len(template.slots)} selected captures")

    capture_paths = []
    for capture_id in request.capture_ids:
        path = CAPTURES.get(capture_id)
        if not path or not path.is_file():
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"capture {capture_id} not found")
        capture_paths.append(path)

    return template, capture_paths


def _build_frame_alpha(template: FrameTemplate) -> Image.Image:
    frame = Image.open(template.file).convert("RGBA")
    rgb = np.asarray(frame.convert("RGB"))
    if template.placeholder == "white":
        placeholder_pixels = (rgb[:, :, 0] > 238) & (rgb[:, :, 1] > 238) & (rgb[:, :, 2] > 238)
    else:
        placeholder_pixels = (rgb[:, :, 0] < 45) & (rgb[:, :, 1] < 45) & (rgb[:, :, 2] < 45)

    alpha = np.full((template.height, template.width), 255, dtype=np.uint8)
    for slot in template.slots:
        y2 = slot.y + slot.height
        x2 = slot.x + slot.width
        alpha[slot.y:y2, slot.x:x2][placeholder_pixels[slot.y:y2, slot.x:x2]] = 0

    frame.putalpha(Image.fromarray(alpha, mode="L"))
    return frame


def _render_collage_image(template: FrameTemplate, capture_paths: list[Path], filter_id: str) -> Image.Image:
    canvas = Image.new("RGBA", (template.width, template.height), (255, 255, 255, 255))

    for capture_path, slot in zip(capture_paths, template.slots, strict=True):
        with Image.open(capture_path) as image:
            image = ImageOps.exif_transpose(image)
            image = _apply_filter(image, filter_id)
            fitted = ImageOps.fit(image, (slot.width, slot.height), method=Image.Resampling.BICUBIC).convert("RGBA")
            canvas.paste(fitted, (slot.x, slot.y), fitted)

    frame = _build_frame_alpha(template)
    canvas.paste(frame, (0, 0), frame)
    return canvas.convert("RGB")


def _render_preview_response(image: Image.Image) -> StreamingResponse:
    image = image.copy()
    image.thumbnail((900, 900), Image.Resampling.LANCZOS)
    output = BytesIO()
    image.save(output, format="JPEG", quality=88)
    output.seek(0)
    return StreamingResponse(output, media_type="image/jpeg")


def _validate_capture_paths(capture_ids: list[UUID]) -> list[Path]:
    capture_paths = []
    for capture_id in capture_ids:
        path = CAPTURES.get(capture_id)
        if not path or not path.is_file():
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"capture {capture_id} not found")
        capture_paths.append(path)
    return capture_paths


def _video_frame_from_capture(capture_path: Path, size: tuple[int, int], filter_id: str) -> np.ndarray:
    with Image.open(capture_path) as image:
        image = ImageOps.exif_transpose(image)
        image = _apply_filter(image, filter_id)
        image = ImageOps.fit(image, size, method=Image.Resampling.BICUBIC).convert("RGB")
        rgb = np.asarray(image)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def _render_timelapse_video(capture_paths: list[Path], filter_id: str) -> Path:
    if filter_id not in {filter_config["id"] for filter_config in FILTERS}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "filter not found")

    TIMELAPSE_DIR.mkdir(parents=True, exist_ok=True)
    timelapse_id = uuid4()
    output_path = TIMELAPSE_DIR / f"{timelapse_id}.webm"

    fps = 30
    size = (1280, 720)
    hold_frames = 13
    transition_frames = 12
    frames = [_video_frame_from_capture(path, size, filter_id) for path in capture_paths]

    writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"VP80"), fps, size)
    if not writer.isOpened():
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "timelapse video encoder is not available")

    try:
        for index, frame in enumerate(frames):
            for _ in range(hold_frames):
                writer.write(frame)

            next_frame = frames[(index + 1) % len(frames)]
            for step in range(transition_frames):
                weight = (step + 1) / (transition_frames + 1)
                blended = cv2.addWeighted(frame, 1 - weight, next_frame, weight, 0)
                writer.write(blended)
    finally:
        writer.release()

    TIMELAPSES[timelapse_id] = output_path
    return output_path


@router.get("/config")
def api_get_framebooth_config():
    templates = _get_templates()
    frame_types = []
    for slot_count in SUPPORTED_FRAME_TYPES:
        matching_templates = [_template_to_public(template) for template in templates.values() if template.frame_type == str(slot_count)]
        matching_templates.sort(key=lambda template: template["name"])
        frame_types.append(
            {
                "slot_count": slot_count,
                "shots_to_take": slot_count + SHOT_BUFFER_COUNT,
                "price": PRICING[slot_count],
                "templates": matching_templates,
            }
        )

    return {
        "shot_buffer_count": SHOT_BUFFER_COUNT,
        "countdown_seconds": CAPTURE_COUNTDOWN_SECONDS,
        "get_ready_seconds": GET_READY_DURATION_SECONDS,
        "payment_mock_seconds": PAYMENT_MOCK_SECONDS,
        "printing_mock_seconds": PRINTING_MOCK_SECONDS,
        "qr_download_seconds": QR_DOWNLOAD_SECONDS,
        "thank_you_seconds": THANK_YOU_SECONDS,
        "digital_delivery_retention_days": DIGITAL_DELIVERY_RETENTION_DAYS,
        "timelapse_render_mock_seconds": TIMELAPSE_RENDER_MOCK_SECONDS,
        "filters": [_filter_to_public(filter_config) for filter_config in FILTERS],
        "frame_types": frame_types,
    }


@router.get("/templates/{template_id}/preview")
def api_get_template_preview(template_id: str):
    template = _get_templates().get(template_id)
    if not template:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "frame template not found")

    return FileResponse(template.file)


@router.post("/templates/{template_id}/composite-preview")
def api_get_template_composite_preview(template_id: str, request: PreviewRequest):
    render_request = RenderRequest(template_id=template_id, capture_ids=request.capture_ids, filter_id=request.filter_id)
    template, capture_paths = _validate_render_request(render_request)
    return _render_preview_response(_render_collage_image(template, capture_paths, render_request.filter_id))


@router.post("/capture")
def api_capture_photo():
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        captured = container.acquisition_service.wait_for_still_file()
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"capture failed: {exc}") from exc

    capture_id = uuid4()
    destination = CAPTURE_DIR / f"{capture_id}{captured.suffix}"
    shutil.copy2(captured, destination)
    CAPTURES[capture_id] = destination

    return {
        "id": str(capture_id),
        "preview_url": f"/api/framebooth/captures/{capture_id}",
    }


@router.get("/captures/{capture_id}")
def api_get_capture(capture_id: UUID):
    path = CAPTURES.get(capture_id)
    if not path or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "capture not found")

    return FileResponse(path)


@router.post("/timelapse")
def api_render_timelapse(request: TimelapseRequest):
    capture_paths = _validate_capture_paths(request.capture_ids)
    output_path = _render_timelapse_video(capture_paths, request.filter_id)
    timelapse_id = UUID(output_path.stem)

    return {
        "id": str(timelapse_id),
        "video_url": f"/api/framebooth/timelapses/{timelapse_id}",
        "status": "ready",
    }


@router.get("/timelapses/{timelapse_id}")
def api_get_timelapse(timelapse_id: UUID):
    path = TIMELAPSES.get(timelapse_id)
    if not path or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "timelapse not found")

    return FileResponse(path, media_type="video/webm")


@router.post("/render")
def api_render_collage(request: RenderRequest):
    template, capture_paths = _validate_render_request(request)
    image = _render_collage_image(template, capture_paths, request.filter_id)

    output_path = Path(PATH_PROCESSED, Path(filename_str_time()).with_suffix(".jpg"))
    image.save(output_path, quality=95)

    mediaitem = Mediaitem(
        id=uuid4(),
        job_identifier=uuid4(),
        media_type="collage",
        processed=output_path,
        pipeline_config={
            "framebooth": True,
            "template_id": template.id,
            "filter_id": request.filter_id,
            "capture_ids": [str(capture_id) for capture_id in request.capture_ids],
            "all_capture_ids": [str(capture_id) for capture_id in request.all_capture_ids],
            "session_id": request.session_id,
            "digital_delivery": request.digital_delivery,
        },
        show_in_gallery=True,
    )
    container.mediacollection_service.add_item(mediaitem)

    return {
        "id": str(mediaitem.id),
        "media_url": f"/media/full/{mediaitem.id}",
        "gallery_url": f"/gallery/mediaviewer/{mediaitem.id}",
        "download_url": f"/gallery/mediaviewer/{mediaitem.id}",
        "retention_days": DIGITAL_DELIVERY_RETENTION_DAYS,
        "timelapse_status": "mock_ready" if request.digital_delivery else "disabled",
    }
