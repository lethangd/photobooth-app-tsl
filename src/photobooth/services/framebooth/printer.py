"""Read the state of the photo printer(s) for the admin dashboard.

Windows uses the spooler via pywin32 (``win32print``), Linux/macOS use CUPS ``lpstat``.
The printer the kiosk prints to is ``printer_name`` of the first share action.
"""

import logging
import shutil
import subprocess
import sys

from ...appconfig import appconfig

logger = logging.getLogger(__name__)

# win32 PRINTER_STATUS_* flags -> (key, Vietnamese label, severity)
_WIN_STATUS_FLAGS: list[tuple[int, str, str, str]] = [
    (0x00000001, "paused", "Tạm dừng", "warning"),
    (0x00000002, "error", "Lỗi", "error"),
    (0x00000004, "pending_deletion", "Đang xoá", "warning"),
    (0x00000008, "paper_jam", "Kẹt giấy", "error"),
    (0x00000010, "paper_out", "Hết giấy", "error"),
    (0x00000020, "manual_feed", "Chờ nạp giấy tay", "warning"),
    (0x00000040, "paper_problem", "Lỗi giấy", "error"),
    (0x00000080, "offline", "Mất kết nối", "error"),
    (0x00000100, "io_active", "Đang truyền dữ liệu", "info"),
    (0x00000200, "busy", "Đang bận", "info"),
    (0x00000400, "printing", "Đang in", "info"),
    (0x00000800, "output_bin_full", "Khay ra đầy", "error"),
    (0x00001000, "not_available", "Không khả dụng", "error"),
    (0x00002000, "waiting", "Đang chờ", "info"),
    (0x00004000, "processing", "Đang xử lý", "info"),
    (0x00008000, "initializing", "Đang khởi động", "info"),
    (0x00010000, "warming_up", "Đang làm nóng", "info"),
    (0x00020000, "toner_low", "Sắp hết mực / ribbon", "warning"),
    (0x00040000, "no_toner", "Hết mực / ribbon", "error"),
    (0x00080000, "page_punt", "Không in được trang", "error"),
    (0x00100000, "user_intervention", "Cần người xử lý", "error"),
    (0x00200000, "out_of_memory", "Hết bộ nhớ", "error"),
    (0x00400000, "door_open", "Mở nắp", "error"),
    (0x00800000, "server_unknown", "Không rõ trạng thái", "warning"),
    (0x01000000, "power_save", "Chế độ tiết kiệm điện", "info"),
]
_WIN_ATTRIBUTE_WORK_OFFLINE = 0x00000400

_SEVERITY_ORDER = {"ok": 0, "info": 1, "warning": 2, "error": 3}


def configured_printer_name() -> str:
    actions = appconfig.share.actions
    return actions[0].processing.printer_name if actions else ""


def _summarize(flags: list[dict], jobs: int) -> tuple[str, str]:
    if not flags:
        return ("ok", f"Sẵn sàng · {jobs} lệnh chờ" if jobs else "Sẵn sàng")
    worst = max(flags, key=lambda flag: _SEVERITY_ORDER[flag["severity"]])
    return worst["severity"], ", ".join(flag["label"] for flag in flags)


def _windows_printers() -> tuple[list[dict], str]:
    import win32print  # noqa: PLC0415  # pywin32 only exists on Windows

    default = ""
    try:
        default = win32print.GetDefaultPrinter()
    except Exception:
        pass

    printers = []
    for info in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS, None, 2):
        status_bits = info.get("Status", 0)
        flags = [{"key": key, "label": label, "severity": severity} for bit, key, label, severity in _WIN_STATUS_FLAGS if status_bits & bit]
        if info.get("Attributes", 0) & _WIN_ATTRIBUTE_WORK_OFFLINE and not any(flag["key"] == "offline" for flag in flags):
            flags.append({"key": "offline", "label": "Mất kết nối", "severity": "error"})
        jobs = int(info.get("cJobs", 0))
        severity, summary = _summarize(flags, jobs)
        printers.append(
            {
                "name": info["pPrinterName"],
                "driver": info.get("pDriverName", ""),
                "port": info.get("pPortName", ""),
                "jobs": jobs,
                "flags": flags,
                "severity": severity,
                "summary": summary,
            }
        )
    return printers, default


def _cups_printers() -> tuple[list[dict], str]:
    if not shutil.which("lpstat"):
        return [], ""
    output = subprocess.run(["lpstat", "-p", "-d"], capture_output=True, text=True, timeout=5).stdout
    default = ""
    printers = []
    for line in output.splitlines():
        if line.startswith("system default destination:"):
            default = line.split(":", 1)[1].strip()
        elif line.startswith("printer "):
            parts = line.split()
            name = parts[1]
            disabled = "disabled" in line
            printing = "now printing" in line
            flags = []
            if disabled:
                flags.append({"key": "offline", "label": "Đã tắt", "severity": "error"})
            elif printing:
                flags.append({"key": "printing", "label": "Đang in", "severity": "info"})
            severity, summary = _summarize(flags, 0)
            printers.append({"name": name, "driver": "", "port": "", "jobs": 0, "flags": flags, "severity": severity, "summary": summary})
    return printers, default


def printer_status() -> dict:
    """All printers known to the OS, the default one, and the state of the one the kiosk prints to."""
    try:
        printers, default = _windows_printers() if sys.platform == "win32" else _cups_printers()
    except Exception as exc:
        logger.warning(f"could not read printer status: {exc}")
        printers, default = [], ""

    configured = configured_printer_name()
    target_name = configured if any(p["name"] == configured for p in printers) else default
    target = next((p for p in printers if p["name"] == target_name), None)

    return {
        "configured_name": configured,
        "default_name": default,
        "kiosk_printer": target,
        "kiosk_printer_found": target is not None,
        "printers": printers,
    }
