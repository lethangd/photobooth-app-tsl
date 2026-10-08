"""HTTP layer for the self-service kiosk ("Framebooth") flow.

All business logic lives in ``photobooth.services.framebooth``; this module only
validates requests, maps domain errors to HTTP responses and shapes the JSON the
kiosk frontend (``web/frontend/framebooth.html``) expects. Business parameters
(pricing, timings, filters) come from ``appconfig.framebooth`` and are editable
from the Admin config page.
"""

import hmac
import logging
import time
from pathlib import Path
from threading import Lock
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ... import PATH_PROCESSED
from ...appconfig import appconfig
from ...container import container
from ...database.models import Mediaitem
from ...services.framebooth import filters, renderer, templates, timelapse
from ...services.framebooth.models import FrameTemplate
from ...services.framebooth.session_store import session_store
from ...utils.helper import filename_str_time

router = APIRouter(prefix="/framebooth", tags=["framebooth"])
logger = logging.getLogger(__name__)


class RenderRequest(BaseModel):
    template_id: str
    capture_ids: list[UUID] = Field(min_length=1)
    all_capture_ids: list[UUID] = Field(default_factory=list)
    filter_id: str = "natural"
    session_id: str | None = None
    digital_delivery: bool = True
    timelapse_id: UUID | None = None


class PreviewRequest(BaseModel):
    capture_ids: list[UUID] = Field(min_length=1)
    filter_id: str = "natural"


class PinRequest(BaseModel):
    pin: str = Field(max_length=16)


# brute-force guard for the staff PIN: after too many wrong tries the kiosk is locked for a while
_PIN_MAX_FAILURES = 5
_PIN_LOCK_SECONDS = 30
_pin_lock = Lock()
_pin_failures = 0
_pin_locked_until = 0.0


class TimelapseRequest(BaseModel):
    capture_ids: list[UUID] = Field(min_length=2)
    filter_id: str = "natural"
    session_id: str | None = None


def _require_template(template_id: str) -> FrameTemplate:
    template = templates.get_template(template_id)
    if not template:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "frame template not found")
    return template


def _require_known_filter(filter_id: str) -> None:
    if filter_id not in filters.get_filter_ids():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "filter not found")


def _resolve_captures(capture_ids: list[UUID]) -> list[Path]:
    capture_paths = session_store.resolve_captures(capture_ids)
    if capture_paths is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "one or more captures not found")
    return capture_paths


def _resolve_render(template_id: str, capture_ids: list[UUID], filter_id: str) -> tuple[FrameTemplate, list[Path]]:
    template = _require_template(template_id)
    _require_known_filter(filter_id)
    if len(capture_ids) != len(template.slots):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"template requires {len(template.slots)} selected captures")
    return template, _resolve_captures(capture_ids)


@router.get("/config")
def api_get_framebooth_config():
    config = appconfig.framebooth
    pricing_by_slot_count = {tier.slot_count: tier.price for tier in config.pricing}

    discovered = templates.get_templates()
    frame_types = []
    for slot_count in templates.SUPPORTED_FRAME_TYPES:
        matching_templates = [templates.template_to_public(t) for t in discovered.values() if t.frame_type == str(slot_count)]
        matching_templates.sort(key=lambda template: template["name"])
        frame_types.append(
            {
                "slot_count": slot_count,
                "shots_to_take": slot_count + config.shot_buffer_count,
                "price": pricing_by_slot_count.get(slot_count, 0),
                "templates": matching_templates,
            }
        )

    return {
        "package_select_timeout_seconds": config.package_select_timeout_seconds,
        "shot_buffer_count": config.shot_buffer_count,
        "countdown_seconds": config.capture_countdown_seconds,
        "get_ready_seconds": config.get_ready_duration_seconds,
        "payment_mock_seconds": config.payment_mock_seconds,
        "payment_timeout_seconds": config.payment_timeout_seconds,
        "photo_select_warn_seconds": config.photo_select_warn_seconds,
        "photo_select_grace_seconds": config.photo_select_grace_seconds,
        "filter_select_warn_seconds": config.filter_select_warn_seconds,
        "filter_select_grace_seconds": config.filter_select_grace_seconds,
        "final_preview_timeout_seconds": config.final_preview_timeout_seconds,
        "printing_mock_seconds": config.printing_mock_seconds,
        "qr_download_seconds": config.qr_download_seconds,
        "thank_you_seconds": config.thank_you_seconds,
        "retake_price": config.retake_price,
        "retake_max_shots": config.retake_max_shots,
        "reduce_motion": config.reduce_motion,
        "sound_enabled": config.sound_enabled,
        "digital_delivery_default_enabled": config.digital_delivery_default_enabled,
        "digital_delivery_retention_days": config.digital_delivery_retention_days,
        "timelapse_render_mock_seconds": config.timelapse_render_mock_seconds,
        "filters": [filters.filter_to_public(filter_config) for filter_config in config.filters],
        "frame_types": frame_types,
    }


@router.post("/verify-pin")
def api_verify_staff_pin(request: PinRequest):
    """Staff confirms a cash/transfer payment by typing the PIN on the kiosk. The PIN never leaves the server."""
    global _pin_failures, _pin_locked_until

    with _pin_lock:
        now = time.monotonic()
        if now < _pin_locked_until:
            return {"ok": False, "locked_seconds": int(_pin_locked_until - now) + 1}

        if hmac.compare_digest(request.pin.encode(), appconfig.framebooth.staff_pin.encode()):
            _pin_failures = 0
            return {"ok": True, "locked_seconds": 0}

        _pin_failures += 1
        logger.warning(f"wrong staff PIN entered ({_pin_failures}/{_PIN_MAX_FAILURES})")
        if _pin_failures >= _PIN_MAX_FAILURES:
            _pin_failures = 0
            _pin_locked_until = now + _PIN_LOCK_SECONDS
            return {"ok": False, "locked_seconds": _PIN_LOCK_SECONDS}
        return {"ok": False, "locked_seconds": 0}


@router.get("/templates/{template_id}/preview")
def api_get_template_preview(template_id: str):
    return FileResponse(_require_template(template_id).file)


@router.post("/templates/{template_id}/composite-preview")
def api_get_template_composite_preview(template_id: str, request: PreviewRequest):
    template, capture_paths = _resolve_render(template_id, request.capture_ids, request.filter_id)
    return renderer.render_preview_response(renderer.render_collage_image(template, capture_paths, request.filter_id))


@router.post("/capture")
def api_capture_photo():
    try:
        captured = container.acquisition_service.wait_for_still_file()
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"capture failed: {exc}") from exc

    capture_id, _ = session_store.add_capture(captured)

    return {
        "id": str(capture_id),
        "preview_url": f"/api/framebooth/captures/{capture_id}",
    }


@router.get("/captures/{capture_id}")
def api_get_capture(capture_id: UUID):
    path = session_store.get_capture(capture_id)
    if not path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "capture not found")
    return FileResponse(path)


@router.post("/timelapse")
def api_render_timelapse(request: TimelapseRequest):
    _require_known_filter(request.filter_id)
    capture_paths = _resolve_captures(request.capture_ids)

    try:
        output_path = timelapse.render_timelapse_video(capture_paths, request.filter_id, session_store.timelapse_dir())
    except timelapse.TimelapseEncoderUnavailableError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc

    timelapse_id = UUID(output_path.stem)
    session_store.register_timelapse(timelapse_id, output_path)

    return {
        "id": str(timelapse_id),
        "video_url": f"/api/framebooth/timelapses/{timelapse_id}",
        "status": "ready",
    }


@router.get("/timelapses/{timelapse_id}")
def api_get_timelapse(timelapse_id: UUID):
    path = session_store.get_timelapse(timelapse_id)
    if not path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "timelapse not found")
    return FileResponse(path, media_type="video/webm")


@router.post("/render")
def api_render_collage(request: RenderRequest):
    template, capture_paths = _resolve_render(request.template_id, request.capture_ids, request.filter_id)
    image = renderer.render_collage_image(template, capture_paths, request.filter_id)

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

    cloud_url = _upload_digital_delivery(request, output_path) if request.digital_delivery else None
    local_url = f"/gallery/mediaviewer/{mediaitem.id}"

    return {
        "id": str(mediaitem.id),
        "media_url": f"/media/full/{mediaitem.id}",
        "gallery_url": local_url,
        "download_url": cloud_url or local_url,
        "cloud_url": cloud_url,
        "retention_days": appconfig.framebooth.digital_delivery_retention_days,
        "timelapse_status": "mock_ready" if request.digital_delivery else "disabled",
    }


def _upload_digital_delivery(request: RenderRequest, collage: Path) -> str | None:
    """Push originals, collage and timelapse to R2. A failed upload must never block the guest's print."""
    cloud = container.cloud_delivery_service
    if not cloud.available:
        return None

    try:
        original_ids = request.all_capture_ids or request.capture_ids
        originals = [path for path in (session_store.get_capture(capture_id) for capture_id in original_ids) if path]
        timelapse = session_store.get_timelapse(request.timelapse_id) if request.timelapse_id else None
        return cloud.upload_session(collage, originals, timelapse)
    except Exception as exc:
        logger.error(f"cloud upload failed, falling back to local gallery link: {exc}")
        return None
