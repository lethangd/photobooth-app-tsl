"""Admin endpoints of the kiosk business: revenue, sessions, staff PIN log, frames, printer, devices."""

import csv
import io
import logging
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from PIL import Image, ImageDraw
from pydantic import BaseModel

from ... import RECYCLE_PATH, TMP_PATH
from ...appconfig import appconfig
from ...container import container
from ...database.models import Mediaitem
from ...services import credentials
from ...services.backends.wigglecam import CALIBRATION_DATA_PATH
from ...services.framebooth import templates
from ...services.framebooth.ledger import ledger
from ...services.framebooth.printer import printer_status
from ...utils.helper import filename_str_time

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/kiosk", tags=["admin", "kiosk"])

_MAX_FRAME_BYTES = 30 * 1024 * 1024
_UTF8_BOM = "﻿"


def _day(value: date | None) -> date:
    return value or date.today()


# ───────── revenue & sessions ─────────


@router.get("/stats")
def api_kiosk_stats(
    day: date | None = None,
    days: Annotated[int, Query(ge=1, le=90)] = 7,
    range_days: Annotated[int, Query(ge=1, le=90)] = 1,
):
    """Totals of the `range_days` days ending at `day` (default today), the same totals of the period before
    (for the "so với hôm qua" comparison) and a daily series of the last `days` days for the chart."""
    last = _day(day)
    first = last - timedelta(days=range_days - 1)
    previous = ledger.period_stats(first - timedelta(days=range_days), first - timedelta(days=1))
    return {
        **ledger.period_stats(first, last),
        "previous": {"revenue": previous["revenue"], "sessions": previous["sessions"]},
        "series": ledger.daily_series(max(days, range_days), last),
    }


@router.get("/sessions")
def api_kiosk_sessions(day: date | None = None, limit: Annotated[int, Query(ge=1, le=1000)] = 200, offset: Annotated[int, Query(ge=0)] = 0):
    return ledger.sessions(_day(day), limit, offset)


@router.get("/sessions.csv")
def api_kiosk_sessions_csv(day: date | None = None):
    """Sessions of a day as CSV (UTF-8 with BOM so Excel shows Vietnamese correctly)."""
    selected = _day(day)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Thời gian", "Mã phiên", "Số ảnh", "Giá gói", "Số lần chụp lại", "Tiền chụp lại", "Tổng", "Đã in lúc", "Ảnh số", "Link ảnh số"])
    for row in reversed(ledger.sessions(selected, limit=1000)):
        digital = "" if row["digital"] is None else ("có" if row["digital"] else "không")
        writer.writerow(
            [
                row["created_at"].replace("T", " "),
                row["session_id"],
                row["slot_count"],
                row["package_price"],
                row["retake_shots"],
                row["retake_amount"],
                row["total"],
                (row["printed_at"] or "").replace("T", " "),
                digital,
                row["cloud_url"] or "",
            ]
        )
    return Response(
        content=(_UTF8_BOM + buffer.getvalue()).encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="doanh-thu-{selected.isoformat()}.csv"'},
    )


@router.get("/sessions/{session_id}")
def api_kiosk_session(session_id: str):
    session = ledger.session(session_id)
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    mediaitem_id = session.get("mediaitem_id")
    session["media_url"] = f"/media/full/{mediaitem_id}" if mediaitem_id else None
    return session


@router.get("/pin-events")
def api_kiosk_pin_events(day: date | None = None, limit: Annotated[int, Query(ge=1, le=1000)] = 200):
    return ledger.pin_events(_day(day), limit)


# ───────── devices ─────────


@router.get("/overview")
def api_kiosk_overview():
    """Health of camera, printer and cloud storage for the dashboard and the devices page."""
    acquisition = container.acquisition_service
    stills = getattr(acquisition, "_stills_backend", None)
    camera_cfg = next((cfg for cfg in appconfig.cameras.group_backends if cfg.enabled), None)
    return {
        "camera": {
            "running": bool(stills and stills.is_running()),
            "backend": type(stills).__name__.removesuffix("Backend") if stills else None,
            "description": camera_cfg.description if camera_cfg else "",
            "device": str(getattr(camera_cfg.backend_config, "device_identifier", "")) if camera_cfg else "",
            "count": len(getattr(acquisition, "_backends", [])),
            "browser_fallback": appconfig.framebooth.browser_camera_fallback,
        },
        "printer": printer_status(),
        "cloud": {
            "enabled": appconfig.framebooth.cloud_delivery_enabled,
            "retention_days": appconfig.framebooth.digital_delivery_retention_days,
            **container.cloud_delivery_service.usage(),
        },
    }


@router.get("/printer")
def api_kiosk_printer():
    return printer_status()


class PrinterSelectRequest(BaseModel):
    name: str


@router.post("/printer/select")
def api_kiosk_printer_select(request: PrinterSelectRequest):
    """Make the kiosk print to another printer (stored as printer_name of the first share action)."""
    if request.name not in {printer["name"] for printer in printer_status()["printers"]}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "printer not found")
    if not appconfig.share.actions:
        raise HTTPException(status.HTTP_409_CONFLICT, "no print action configured")
    appconfig.share.actions[0].processing.printer_name = request.name
    appconfig.persist()
    return printer_status()


def _print(mediaitem: Mediaitem) -> None:
    try:
        container.share_service.share(mediaitem, 0)
    except Exception as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Không gửi được lệnh in: {exc}") from exc


@router.post("/printer/test", status_code=status.HTTP_202_ACCEPTED)
def api_kiosk_printer_test():
    """Send a small 4x6 test page through the regular print command."""
    path = Path(TMP_PATH, f"printer-test-{filename_str_time()}.jpg")
    path.parent.mkdir(parents=True, exist_ok=True)
    page = Image.new("RGB", (1200, 1800), "#FFFFFF")
    draw = ImageDraw.Draw(page)
    draw.rectangle([60, 60, 1140, 1740], outline="#2B3BFF", width=24)
    for index, color in enumerate(["#2B3BFF", "#C9B8FF", "#A8F0E0", "#FFD2B8", "#14161C"]):
        draw.rectangle([140 + index * 190, 300, 300 + index * 190, 1300], fill=color)
    draw.text((140, 1450), "TSL PHOTOBOOTH - IN THU", fill="#14161C", font_size=72)
    page.save(path, quality=92)
    _print(Mediaitem(id=uuid4(), job_identifier=uuid4(), media_type="image", processed=path, pipeline_config={}, show_in_gallery=False))
    return {"ok": True}


@router.post("/sessions/{session_id}/print", status_code=status.HTTP_202_ACCEPTED)
def api_kiosk_reprint(session_id: str):
    """Print the collage of a session again (uses the first share/print action)."""
    session = ledger.session(session_id)
    if not session or not session.get("mediaitem_id"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session has no printed photo")
    try:
        mediaitem = container.mediacollection_service.get_item(UUID(session["mediaitem_id"]))
    except Exception as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "photo of this session no longer exists") from exc
    _print(mediaitem)
    return {"ok": True}


@router.get("/multicam")
def api_kiosk_multicam():
    """Wigglecam nodes from the camera config and whether a calibration is stored."""
    nodes = []
    for cfg in appconfig.cameras.group_backends:
        backend = cfg.backend_config
        if getattr(backend, "backend_type", "") == "Wigglecam":
            nodes = [
                {"index": i, "description": node.description, "address": f"{node.address}:{node.base_port}"} for i, node in enumerate(backend.devices)
            ]
            break
    calibration = Path(CALIBRATION_DATA_PATH)
    calibrated = calibration.is_file() or (calibration.is_dir() and any(calibration.iterdir()))
    duration = appconfig.actions.multicamera[0].processing.duration if appconfig.actions.multicamera else 125
    return {"configured": bool(nodes), "nodes": nodes, "calibrated": calibrated, "frame_duration_ms": duration}


# ───────── frames ─────────


@router.get("/frames")
def api_kiosk_frames():
    result = []
    for template in sorted(templates.get_templates().values(), key=lambda t: (t.frame_type, t.file.name)):
        result.append(
            {
                **templates.template_to_public(template),
                "file_name": template.file.name,
                "file_size": template.file.stat().st_size if template.file.exists() else 0,
                "placeholder": template.placeholder,
                "slots": [slot.model_dump() for slot in template.slots],
            }
        )
    return result


@router.post("/frames", status_code=status.HTTP_201_CREATED)
async def api_kiosk_upload_frame(file: UploadFile, slot_count: Annotated[int, Form()]):
    """Add a frame image. The photo slots (solid white or black boxes) must be detectable, otherwise it is rejected."""
    if slot_count not in templates.SUPPORTED_FRAME_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"slot_count must be one of {templates.SUPPORTED_FRAME_TYPES}")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in templates._SUPPORTED_SUFFIXES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "only JPG, PNG or WebP frames are supported")
    content = await file.read()
    if not content or len(content) > _MAX_FRAME_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "empty or too large file")

    folder = templates.FRAME_DIR / str(slot_count)
    folder.mkdir(parents=True, exist_ok=True)
    safe_stem = "".join(char if char.isalnum() or char in "-_" else "-" for char in Path(file.filename or "frame").stem).strip("-") or "frame"
    target = folder / f"{safe_stem}{suffix}"
    if target.exists():
        target = folder / f"{safe_stem}-{filename_str_time()}{suffix}"

    target.write_bytes(content)
    try:
        placeholder, slots = templates.detect_slots(target, slot_count)
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Không tìm thấy đủ {slot_count} ô ảnh trong khung. Các ô phải là hình chữ nhật trắng hoặc đen đặc. ({exc})",
        ) from exc

    templates.invalidate_templates_cache()
    logger.info(f"frame {target.name} added with {len(slots)} {placeholder} slots")
    return {"file_name": target.name, "slot_count": slot_count, "placeholder": placeholder, "slots": [slot.model_dump() for slot in slots]}


@router.delete("/frames/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def api_kiosk_delete_frame(template_id: str):
    """Move a frame to the recycle folder (it can be restored by moving the file back)."""
    template = templates.get_template(template_id)
    if not template:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "frame not found")
    Path(RECYCLE_PATH).mkdir(parents=True, exist_ok=True)
    shutil.move(str(template.file), Path(RECYCLE_PATH, f"frame-{template.frame_type}-{filename_str_time()}-{template.file.name}"))
    templates.invalidate_templates_cache()


# ───────── admin password & staff PIN (kept hashed in .env) ─────────


class PasswordChange(BaseModel):
    current_password: str
    new_value: str


@router.get("/security")
def api_kiosk_security():
    return {
        "admin_password_default": credentials.admin_password_is_default(),
        "staff_pin_default": credentials.staff_pin_is_default(),
        "secrets_file": str(credentials.secrets_file().resolve()),
        # automatic confirmation of bank transfers (see services/framebooth/payments.py)
        "sepay": "token" if credentials.get_value("SEPAY_API_TOKEN") else ("webhook" if credentials.get_value("SEPAY_WEBHOOK_KEY") else None),
    }


def _change(body: PasswordChange, setter) -> dict:
    # re-ask the admin password so an unattended logged-in browser cannot change it
    if not credentials.verify_admin_password(body.current_password):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Mật khẩu admin hiện tại không đúng")
    try:
        setter(body.new_value)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return api_kiosk_security()


@router.post("/security/admin-password")
def api_kiosk_set_admin_password(body: PasswordChange):
    return _change(body, credentials.set_admin_password)


@router.post("/security/staff-pin")
def api_kiosk_set_staff_pin(body: PasswordChange):
    return _change(body, credentials.set_staff_pin)
