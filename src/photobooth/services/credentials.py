"""Secrets of the app kept out of ``config/config.json``: the admin password, the staff PIN and the
key signing admin login tokens.

They live in ``.env`` in the working directory (git-ignored, override the path with the
``PHOTOBOOTH_SECRETS_FILE`` environment variable). Passwords and PINs are stored as salted
PBKDF2-SHA256 hashes, never in clear text::

    ADMIN_PASSWORD_HASH=pbkdf2_sha256$310000$<salt>$<hash>
    STAFF_PIN_HASH=pbkdf2_sha256$310000$<salt>$<hash>
    AUTH_TOKEN_SECRET=<random hex>

Values already set in the process environment win over the file (useful for Docker/systemd).
Until a password / PIN is set, the factory defaults "0000" / "1234" are accepted and reported
as such so the admin dashboard can ask to change them.
"""

import base64
import hashlib
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

ADMIN_PASSWORD_KEY = "ADMIN_PASSWORD_HASH"
STAFF_PIN_KEY = "STAFF_PIN_HASH"
TOKEN_SECRET_KEY = "AUTH_TOKEN_SECRET"

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 310_000
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
    try:
        os.chmod(path, 0o600)  # owner only; no effect on Windows ACLs
    except OSError:
        pass


def _get(key: str) -> str:
    return os.environ.get(key) or _read_file().get(key, "")


# ───────── hashing ─────────


def hash_secret(plain: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, _ITERATIONS)
    return f"{_ALGORITHM}${_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_secret(plain: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, digest = stored.split("$")
        if algorithm != _ALGORITHM:
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), base64.b64decode(salt), int(iterations))
        return hmac.compare_digest(candidate, base64.b64decode(digest))
    except (ValueError, TypeError):
        return False


# ───────── public API ─────────


def verify_admin_password(plain: str) -> bool:
    stored = _get(ADMIN_PASSWORD_KEY)
    if not stored:
        return hmac.compare_digest(plain.encode(), DEFAULT_ADMIN_PASSWORD.encode())
    return verify_secret(plain, stored)


def verify_staff_pin(plain: str) -> bool:
    stored = _get(STAFF_PIN_KEY)
    if not stored:
        return hmac.compare_digest(plain.encode(), DEFAULT_STAFF_PIN.encode())
    return verify_secret(plain, stored)


def set_admin_password(plain: str) -> None:
    if len(plain) < 6:
        raise ValueError("Mật khẩu admin cần ít nhất 6 ký tự")
    with _lock:
        _write_value(ADMIN_PASSWORD_KEY, hash_secret(plain))
    logger.info(f"admin password changed (stored hashed in {secrets_file()})")


def set_staff_pin(plain: str) -> None:
    if len(plain) != 4 or not plain.isdigit():
        raise ValueError("PIN nhân viên phải gồm đúng 4 chữ số")
    with _lock:
        _write_value(STAFF_PIN_KEY, hash_secret(plain))
    logger.info(f"staff PIN changed (stored hashed in {secrets_file()})")


def admin_password_is_default() -> bool:
    return not _get(ADMIN_PASSWORD_KEY)


def staff_pin_is_default() -> bool:
    return not _get(STAFF_PIN_KEY)


def token_secret() -> str:
    """Key signing admin login tokens; created once so logins survive restarts."""
    value = _get(TOKEN_SECRET_KEY)
    if value:
        return value
    with _lock:
        value = _read_file().get(TOKEN_SECRET_KEY, "")
        if not value:
            value = secrets.token_hex(32)
            _write_value(TOKEN_SECRET_KEY, value)
    return value


def migrate_from_config_file() -> None:
    """Move secrets an older version stored in clear text in config.json into .env (hashed) and drop them there."""
    config_file = Path(CONFIG_PATH, "config.json")
    if not config_file.is_file():
        return
    try:
        data = json.loads(config_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return

    changed = False
    password = (data.get("common") or {}).pop("admin_password", None)
    if password is not None:
        changed = True
        if password not in ("", DEFAULT_ADMIN_PASSWORD, "************") and admin_password_is_default():
            with _lock:
                _write_value(ADMIN_PASSWORD_KEY, hash_secret(str(password)))
    pin = (data.get("framebooth") or {}).pop("staff_pin", None)
    if pin is not None:
        changed = True
        if pin not in ("", DEFAULT_STAFF_PIN) and staff_pin_is_default():
            with _lock:
                _write_value(STAFF_PIN_KEY, hash_secret(str(pin)))
    token = (data.get("misc") or {}).pop("secret", None)
    if token is not None:
        changed = True
        if not _get(TOKEN_SECRET_KEY):
            with _lock:
                _write_value(TOKEN_SECRET_KEY, str(token))

    if changed:
        config_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"moved admin password, staff PIN and token secret from {config_file} to {secrets_file()}")
