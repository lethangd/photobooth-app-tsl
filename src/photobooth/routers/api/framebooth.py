"""HTTP layer for the self-service kiosk ("Framebooth") flow.

All business logic lives in ``photobooth.services.framebooth``; this module only
validates requests, maps domain errors to HTTP responses and shapes the JSON the
kiosk frontend (``web/frontend/framebooth.html``) expects. Business parameters
(pricing, timings, filters) come from ``appconfig.framebooth`` and are editable
from the Admin config page.
"""

import hmac
import io
import logging
import tempfile
import time
from pathlib import Path
from threading import Lock
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from ... import PATH_PROCESSED
from ...appconfig import appconfig
from ...container import container
from ...database.models import Mediaitem
from ...services import credentials
from ...services.framebooth import filters, printer, renderer, templates, timelapse
from ...services.framebooth import payments as payments_module
from ...services.framebooth.ledger import ledger
from ...services.framebooth.models import FrameTemplate
from ...services.framebooth.payments import SEPAY_WEBHOOK_KEY, PaymentError, add_loyalty_stamp, check_voucher, list_amount, payments
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
    copies: int = Field(default=1, ge=1, le=10)
    share_consent: bool = False
    # transparent PNG drawn on the kiosk (stickers, text, doodles), laid over the whole collage
    overlay_png: str | None = Field(default=None, max_length=12_000_000)


class PreviewRequest(BaseModel):
    capture_ids: list[UUID] = Field(min_length=1)
    filter_id: str = "natural"


class PinRequest(BaseModel):
    pin: str = Field(max_length=16)
    # what the staff confirms; the amount is derived from the server-side prices
    session_id: str | None = Field(default=None, max_length=64)
    purpose: Literal["package", "retake", "copies"] = "package"
    slot_count: int | None = None
    retake_shots: int | None = Field(default=None, ge=1, le=20)
    # the payment request the staff confirms (preferred: carries discount and partial transfers)
    reference: str | None = Field(default=None, max_length=32)


def _pin_amount(request: PinRequest) -> int:
    intent = payments.get(request.reference) if request.reference else None
    if intent:
        return intent.remaining
    config = appconfig.framebooth
    if request.purpose == "retake":
        return (request.retake_shots or 0) * config.retake_price
    return next((tier.price for tier in config.pricing if tier.slot_count == request.slot_count), 0)


def _record_pin(request: PinRequest, ok: bool, locked: bool = False) -> None:
    """Revenue/PIN bookkeeping must never break the guest flow."""
    amount = _pin_amount(request)
    try:
        ledger.record_pin(request.session_id, request.purpose, amount, ok, locked)
        if ok and request.reference and payments.get(request.reference):
            payments.confirm_by_staff(request.reference)  # books the payment itself
        elif ok and request.session_id and request.purpose != "copies":
            if request.purpose == "retake":
                ledger.record_retake_paid(request.session_id, request.retake_shots or 0, amount)
            else:
                ledger.record_package_paid(request.session_id, request.slot_count or 0, amount)
    except Exception as exc:
        logger.error(f"could not write kiosk ledger: {exc}")


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
        "browser_camera_fallback": config.browser_camera_fallback,
        "digital_delivery_default_enabled": config.digital_delivery_default_enabled,
        "digital_delivery_retention_days": config.digital_delivery_retention_days,
        "timelapse_render_mock_seconds": config.timelapse_render_mock_seconds,
        "pose_seconds_options": config.pose_seconds_options,
        "payment_qr_expiry_seconds": config.payment_qr_expiry_seconds,
        "bank_qr": payments_module.bank_qr_configured(),
        "auto_confirm": payments_module.auto_confirm_available(),
        "extra_copy_price": config.extra_copy_price,
        "max_print_copies": config.max_print_copies,
        "print_enabled": config.print_enabled,
        "loyalty_enabled": config.loyalty_enabled,
        "loyalty_stamps_for_reward": config.loyalty_stamps_for_reward,
        "support_hotline": config.support_hotline,
        "has_vouchers": any(voucher.enabled for voucher in config.vouchers) or config.loyalty_enabled,
        "filters": [filters.filter_to_public(filter_config) for filter_config in config.filters],
        "frame_types": frame_types,
    }


# ───────── payments, vouchers, loyalty ─────────


class PaymentRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    purpose: Literal["package", "retake", "copies"] = "package"
    quantity: int = Field(ge=1, le=20, description="slot count for a package, shots for a retake, extra copies for copies")
    voucher_code: str | None = Field(default=None, max_length=24)


class VoucherCheck(BaseModel):
    code: str = Field(max_length=24)
    slot_count: int


class LoyaltyRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    phone: str = Field(max_length=20)


class FeedbackRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    rating: int | None = Field(default=None, ge=1, le=3)
    # guest allows the shop to post the photo on its page
    share_consent: bool | None = None


def _payment_or_404(reference: str):
    intent = payments.get(reference)
    if not intent:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "payment not found")
    return intent


@router.post("/payments")
def api_create_payment(request: PaymentRequest):
    """Amount to pay (server prices, discount applied) and the VietQR text for it."""
    try:
        return payments.create(request.session_id, request.purpose, request.quantity, request.voucher_code).public()
    except PaymentError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


@router.get("/payments/{reference}")
def api_get_payment(reference: str):
    return _payment_or_404(reference).public()


@router.post("/payments/{reference}/renew")
def api_renew_payment(reference: str):
    _payment_or_404(reference)
    return payments.renew(reference).public()


@router.post("/payments/{reference}/cancel")
def api_cancel_payment(reference: str):
    _payment_or_404(reference)
    payments.cancel(reference)
    return {"ok": True}


@router.post("/vouchers/check")
def api_check_voucher(request: VoucherCheck):
    try:
        base = list_amount("package", request.slot_count)
        discount = check_voucher(request.code, "package", base)
    except PaymentError as exc:
        return {"ok": False, "message": str(exc)}
    return {"ok": True, "code": discount.code, "discount": discount.amount, "total": base - discount.amount, "label": discount.label}


@router.post("/payments/sepay-webhook")
async def api_sepay_webhook(request: Request, authorization: str = Header(default="")):
    """Webhook of SePay (https://sepay.vn) for every incoming transfer; needs SEPAY_WEBHOOK_KEY in .env."""
    key = credentials.get_value(SEPAY_WEBHOOK_KEY)
    if not key or not hmac.compare_digest(authorization.encode(), f"Apikey {key}".encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid api key")
    body = await request.json()
    if body.get("transferType") == "in" and int(body.get("transferAmount") or 0) > 0:
        payments.apply_transfer(f"sepay-{body.get('id')}", int(body["transferAmount"]), str(body.get("content") or ""))
    return {"success": True}


@router.post("/loyalty")
def api_loyalty_stamp(request: LoyaltyRequest):
    if not appconfig.framebooth.loyalty_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "loyalty disabled")
    try:
        return add_loyalty_stamp(request.phone, request.session_id)
    except PaymentError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


@router.post("/feedback")
def api_feedback(request: FeedbackRequest):
    try:
        if request.rating is not None:
            ledger.record_session_field(request.session_id, "rating", request.rating)
        if request.share_consent is not None:
            ledger.record_session_field(request.session_id, "share_consent", int(request.share_consent))
    except Exception as exc:
        logger.error(f"could not write kiosk ledger: {exc}")
    return {"ok": True}


# ───────── printer ─────────


class PrintRequest(BaseModel):
    media_id: UUID
    copies: int = Field(default=1, ge=1, le=10)
    session_id: str | None = None


@router.get("/printer-status")
def api_printer_status():
    """Short state of the kiosk printer for the device-error screen (polls until it can print again)."""
    return printer.kiosk_printer_problem() or {"ok": True}


@router.post("/print")
def api_print_again(request: PrintRequest):
    try:
        mediaitem = container.mediacollection_service.get_item(request.media_id)
    except Exception as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "photo not found") from exc
    return _print(mediaitem, request.copies, request.session_id)


def _print(mediaitem: Mediaitem, copies: int, session_id: str | None) -> dict:
    if not appconfig.framebooth.print_enabled:
        return {"ok": True, "simulated": True}
    problem = printer.print_media(mediaitem, copies)
    if problem and session_id:
        try:
            ledger.record_session_field(session_id, "print_error", problem["code"])
        except Exception as exc:
            logger.error(f"could not write kiosk ledger: {exc}")
    return problem or {"ok": True, "simulated": False}


@router.post("/verify-pin")
def api_verify_staff_pin(request: PinRequest):
    """Staff confirms a cash/transfer payment by typing the PIN on the kiosk. The PIN never leaves the server."""
    global _pin_failures, _pin_locked_until

    with _pin_lock:
        now = time.monotonic()
        if now < _pin_locked_until:
            _record_pin(request, ok=False, locked=True)
            return {"ok": False, "locked_seconds": int(_pin_locked_until - now) + 1}

        if credentials.verify_staff_pin(request.pin):
            _pin_failures = 0
            _record_pin(request, ok=True)
            return {"ok": True, "locked_seconds": 0}

        _pin_failures += 1
        logger.warning(f"wrong staff PIN entered ({_pin_failures}/{_PIN_MAX_FAILURES})")
        if _pin_failures >= _PIN_MAX_FAILURES:
            _pin_failures = 0
            _pin_locked_until = now + _PIN_LOCK_SECONDS
            _record_pin(request, ok=False, locked=True)
            return {"ok": False, "locked_seconds": _PIN_LOCK_SECONDS}
        _record_pin(request, ok=False)
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


_MAX_UPLOAD_BYTES = 25 * 1024 * 1024


@router.get("/camera-status")
def api_camera_status():
    """Lets the kiosk fall back to the browser camera (laptop webcam / phone) when the server camera is unusable."""
    acquisition = container.acquisition_service
    # "virtual": only the demo camera is configured, no real one connected -> the kiosk uses the browser camera if it can
    return {"available": acquisition.stills_camera_ready(), "virtual": acquisition.stills_camera_is_virtual()}


@router.post("/captures/upload")
async def api_upload_capture(request: Request):
    """Store a photo taken by the browser camera (raw JPEG/PNG body) as a capture of the current session."""
    body = await request.body()
    if not body or len(body) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "empty or too large image")
    try:
        with Image.open(io.BytesIO(body)) as probe:
            probe.verify()
            suffix = ".png" if probe.format == "PNG" else ".jpg"
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "not an image") from exc

    with tempfile.TemporaryDirectory() as tmp_dir:
        upload = Path(tmp_dir, f"{filename_str_time()}_browser{suffix}")
        upload.write_bytes(body)
        capture_id, _ = session_store.add_capture(upload)

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
    if request.overlay_png:
        image = renderer.apply_overlay(image, request.overlay_png)

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
            "copies": request.copies,
        },
        show_in_gallery=True,
    )
    container.mediacollection_service.add_item(mediaitem)

    # print first: the guest is waiting at the printer, the upload can take a few seconds
    print_result = _print(mediaitem, request.copies, request.session_id)
    cloud_url = _upload_digital_delivery(request, output_path) if request.digital_delivery else None
    local_url = f"/gallery/mediaviewer/{mediaitem.id}"
    try:
        ledger.record_print(request.session_id, str(mediaitem.id), request.digital_delivery, cloud_url)
        if request.session_id:
            ledger.record_session_field(request.session_id, "share_consent", int(request.share_consent))
    except Exception as exc:
        logger.error(f"could not write kiosk ledger: {exc}")

    return {
        "id": str(mediaitem.id),
        "media_url": f"/media/full/{mediaitem.id}",
        "gallery_url": local_url,
        "download_url": cloud_url or local_url,
        "cloud_url": cloud_url,
        "retention_days": appconfig.framebooth.digital_delivery_retention_days,
        "timelapse_status": "mock_ready" if request.digital_delivery else "disabled",
        "print": print_result,
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
        selected = [path for path in (session_store.get_capture(capture_id) for capture_id in request.capture_ids) if path]
        return cloud.upload_session(collage, originals, timelapse, boomerang_sources=selected, session_id=request.session_id)
    except Exception as exc:
        logger.error(f"cloud upload failed, falling back to local gallery link: {exc}")
        return None
