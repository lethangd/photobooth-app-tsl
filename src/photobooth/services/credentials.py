"""Secrets of the app kept out of ``config/config.json``: the admin password, the staff PIN and the
key signing admin login tokens.

They live in ``.env`` in the working directory (git-ignored, see ``.env.example``; override the path
with the ``PHOTOBOOTH_SECRETS_FILE`` environment variable)::

    ADMIN_PASSWORD=0000
    STAFF_PIN=1234
    AUTH_TOKEN_SECRET=<random hex>

Values already set in the process environment win over the file (useful for Docker/systemd).
Until a password / PIN is set, the factory defaults "0000" / "1234" are used and reported as such
so the admin dashboard can ask to change them.
"""

import hmac
import json
import logging
import os
import secrets
import threading
from pathlib import Path

from .. import CONFIG_PATH

logger = logging.getLogger(__name__)

DEFAULT_ADMIN_PASSWORD = "0000"
DEFAULT_STAFF_PIN = "1234"

ADMIN_PASSWORD_KEY = "ADMIN_PASSWORD"
STAFF_PIN_KEY = "STAFF_PIN"
TOKEN_SECRET_KEY = "AUTH_TOKEN_SECRET"

_lock = threading.Lock()


def secrets_file() -> Path:
    return Path(os.environ.get("PHOTOBOOTH_SECRETS_FILE", ".env"))


# ───────── .env file ─────────


def _read_file() -> dict[str, str]:
    path = secrets_file()
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key and not key.startswith("#"):
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _write_value(key: str, value: str) -> None:
    """Set one KEY=value in the file, keeping every other line (comments included) as it is."""
    with _lock:
        path = secrets_file()
        lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
        replaced = False
        for index, line in enumerate(lines):
            if line.strip().partition("=")[0].strip() == key:
                lines[index] = f"{key}={value}"
                replaced = True
        if not replaced:
            lines.append(f"{key}={value}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _get(key: str) -> str:
    return os.environ.get(key) or _read_file().get(key, "")


def get_value(key: str) -> str:
    """Any other setting of the .env file (environment first), e.g. SEPAY_API_TOKEN."""
    return _get(key)


def _matches(plain: str, expected: str) -> bool:
    return hmac.compare_digest(plain.encode("utf-8"), expected.encode("utf-8"))


# ───────── public API ─────────


def verify_admin_password(plain: str) -> bool:
    return _matches(plain, _get(ADMIN_PASSWORD_KEY) or DEFAULT_ADMIN_PASSWORD)


def verify_staff_pin(plain: str) -> bool:
    return _matches(plain, _get(STAFF_PIN_KEY) or DEFAULT_STAFF_PIN)


def set_admin_password(plain: str) -> None:
    if len(plain) < 6:
        raise ValueError("Mật khẩu admin cần ít nhất 6 ký tự")
    _write_value(ADMIN_PASSWORD_KEY, plain)
    logger.info(f"admin password changed (saved in {secrets_file()})")


def set_staff_pin(plain: str) -> None:
    if len(plain) != 4 or not plain.isdigit():
        raise ValueError("PIN nhân viên phải gồm đúng 4 chữ số")
    _write_value(STAFF_PIN_KEY, plain)
    logger.info(f"staff PIN changed (saved in {secrets_file()})")


def admin_password_is_default() -> bool:
    return (_get(ADMIN_PASSWORD_KEY) or DEFAULT_ADMIN_PASSWORD) == DEFAULT_ADMIN_PASSWORD


def staff_pin_is_default() -> bool:
    return (_get(STAFF_PIN_KEY) or DEFAULT_STAFF_PIN) == DEFAULT_STAFF_PIN


def token_secret() -> str:
    """Key signing admin login tokens; created once so logins survive restarts."""
    value = _get(TOKEN_SECRET_KEY)
    if not value:
        value = secrets.token_hex(32)
        _write_value(TOKEN_SECRET_KEY, value)
    return value


def migrate_from_config_file() -> None:
    """Move secrets an older version stored in config.json into .env and drop them there."""
    config_file = Path(CONFIG_PATH, "config.json")
    if not config_file.is_file():
        return
    try:
        data = json.loads(config_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return

    moves = [
        ("common", "admin_password", ADMIN_PASSWORD_KEY, DEFAULT_ADMIN_PASSWORD),
        ("framebooth", "staff_pin", STAFF_PIN_KEY, DEFAULT_STAFF_PIN),
        ("misc", "secret", TOKEN_SECRET_KEY, ""),
    ]
    changed = False
    for group, field, key, default in moves:
        value = (data.get(group) or {}).pop(field, None)
        if value is None:
            continue
        changed = True
        if str(value) not in ("", default, "************") and not _get(key):
            _write_value(key, str(value))

    if changed:
        config_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"moved admin password, staff PIN and token secret from {config_file} to {secrets_file()}")
