import json
from pathlib import Path

import pytest

from photobooth.services import credentials


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("PHOTOBOOTH_SECRETS_FILE", str(tmp_path / ".env"))
    monkeypatch.setattr(credentials, "CONFIG_PATH", str(tmp_path))
    for key in (credentials.ADMIN_PASSWORD_KEY, credentials.STAFF_PIN_KEY, credentials.TOKEN_SECRET_KEY):
        monkeypatch.delenv(key, raising=False)
    return tmp_path


def test_hash_roundtrip():
    stored = credentials.hash_secret("abc123")
    assert stored.startswith("pbkdf2_sha256$") and "abc123" not in stored
    assert credentials.verify_secret("abc123", stored)
    assert not credentials.verify_secret("abc124", stored)
    assert not credentials.verify_secret("abc123", "garbage")


def test_defaults_until_set(isolated: Path):
    assert credentials.verify_admin_password("0000") and credentials.admin_password_is_default()
    assert credentials.verify_staff_pin("1234") and credentials.staff_pin_is_default()
    with pytest.raises(ValueError):
        credentials.set_admin_password("123")


def test_token_secret_is_created_once_and_keeps_other_lines(isolated: Path):
    (isolated / ".env").write_text("# my settings\nR2_BUCKET=demo\n", encoding="utf-8")
    first = credentials.token_secret()
    assert first == credentials.token_secret()
    content = (isolated / ".env").read_text(encoding="utf-8")
    assert "# my settings" in content and "R2_BUCKET=demo" in content and f"AUTH_TOKEN_SECRET={first}" in content


def test_environment_wins_over_file(isolated: Path, monkeypatch: pytest.MonkeyPatch):
    credentials.set_staff_pin("1111")
    monkeypatch.setenv("STAFF_PIN_HASH", credentials.hash_secret("2222"))
    assert credentials.verify_staff_pin("2222") and not credentials.verify_staff_pin("1111")


def test_migrate_from_config_json(isolated: Path):
    config = {
        "common": {"admin_password": "old-pass", "logging_level": "INFO"},
        "framebooth": {"staff_pin": "9876"},
        "misc": {"secret": "abcdef0123456789"},
    }
    (isolated / "config.json").write_text(json.dumps(config), encoding="utf-8")

    credentials.migrate_from_config_file()

    migrated = json.loads((isolated / "config.json").read_text(encoding="utf-8"))
    assert migrated == {"common": {"logging_level": "INFO"}, "framebooth": {}, "misc": {}}
    assert credentials.verify_admin_password("old-pass") and credentials.verify_staff_pin("9876")
    assert credentials.token_secret() == "abcdef0123456789"
    assert "old-pass" not in (isolated / ".env").read_text(encoding="utf-8")
