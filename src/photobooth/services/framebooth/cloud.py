"""Cloudflare R2 delivery of the digital files (originals, collage, timelapse) of a kiosk session.

Credentials are read from environment variables, optionally preloaded from a ``.env.r2`` file in the
working directory (git-ignored) so secrets never end up in ``config.json``::

    R2_ENDPOINT, R2_BUCKET, R2_PUBLIC_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY

Each session is uploaded below an unguessable prefix ``sessions/<token>/`` together with a small
``index.html`` page that the QR code links to. A background sweeper deletes sessions older than
``appconfig.framebooth.digital_delivery_retention_days``.
"""

import logging
import mimetypes
import os
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html import escape
from pathlib import Path

from ...appconfig import appconfig
from ...utils.repeatedtimer import RepeatedTimer
from ..base import BaseService

logger = logging.getLogger(__name__)

ENV_FILE = Path(".env.r2")
SESSIONS_PREFIX = "sessions/"
SWEEP_INTERVAL_SECONDS = 60 * 60
UPLOAD_WORKERS = 4


@dataclass(frozen=True)
class R2Settings:
    endpoint: str
    bucket: str
    public_url: str
    access_key_id: str
    secret_access_key: str

    @classmethod
    def load(cls) -> "R2Settings | None":
        env = dict(os.environ)
        if ENV_FILE.is_file():
            for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
                key, sep, value = line.strip().partition("=")
                if sep and not key.startswith("#"):
                    env.setdefault(key.strip(), value.strip())

        try:
            return cls(
                endpoint=env["R2_ENDPOINT"],
                bucket=env["R2_BUCKET"],
                public_url=env["R2_PUBLIC_URL"].rstrip("/"),
                access_key_id=env["R2_ACCESS_KEY_ID"],
                secret_access_key=env["R2_SECRET_ACCESS_KEY"],
            )
        except KeyError:
            return None


class CloudDeliveryService(BaseService):
    def __init__(self) -> None:
        super().__init__()
        self._settings: R2Settings | None = None
        self._client = None
        self._sweep_timer = RepeatedTimer(SWEEP_INTERVAL_SECONDS, self.sweep_expired)

    @property
    def available(self) -> bool:
        return self._client is not None

    def start(self):
        super().start()

        if not appconfig.framebooth.cloud_delivery_enabled:
            logger.info("cloud delivery disabled in config")
            self.disabled()
            return

        self._settings = R2Settings.load()
        if self._settings is None:
            logger.warning("cloud delivery enabled but R2_* credentials missing (env or .env.r2), staying disabled")
            self.disabled()
            return

        import boto3  # noqa: PLC0415  # lazy: only needed when cloud delivery is configured
        from botocore.config import Config  # noqa: PLC0415

        self._client = boto3.client(
            "s3",
            endpoint_url=self._settings.endpoint,
            aws_access_key_id=self._settings.access_key_id,
            aws_secret_access_key=self._settings.secret_access_key,
            region_name="auto",
            config=Config(retries={"max_attempts": 3, "mode": "standard"}, connect_timeout=10, read_timeout=60),
        )

        self._sweep_timer.start()
        # initial sweep off the main thread so a slow network never delays boot
        ThreadPoolExecutor(max_workers=1).submit(self.sweep_expired)

        super().started()
        logger.info(f"cloud delivery ready, bucket {self._settings.bucket}")

    def stop(self):
        super().stop()
        self._sweep_timer.stop()
        self._client = None
        super().stopped()

    def upload_session(
        self,
        collage: Path,
        originals: list[Path],
        timelapse: Path | None = None,
    ) -> str:
        """Upload one session and return the public URL of its landing page. Raises on failure."""
        assert self._client and self._settings, "cloud delivery not available"

        token = secrets.token_urlsafe(16)
        prefix = f"{SESSIONS_PREFIX}{token}/"
        retention_days = appconfig.framebooth.digital_delivery_retention_days

        files: list[tuple[Path, str]] = [(collage, f"collage{collage.suffix}")]
        files += [(path, f"original_{index}{path.suffix}") for index, path in enumerate(originals, start=1)]
        if timelapse:
            files.append((timelapse, f"timelapse{timelapse.suffix}"))

        with ThreadPoolExecutor(max_workers=UPLOAD_WORKERS) as pool:
            list(pool.map(lambda item: self._put_file(prefix + item[1], item[0]), files))

        index_html = self._render_index(
            collage=files[0][1],
            originals=[name for _, name in files[1 : 1 + len(originals)]],
            timelapse=files[-1][1] if timelapse else None,
            expires=datetime.now(UTC) + timedelta(days=retention_days),
        )
        self._client.put_object(
            Bucket=self._settings.bucket,
            Key=prefix + "index.html",
            Body=index_html.encode("utf-8"),
            ContentType="text/html; charset=utf-8",
        )

        url = f"{self._settings.public_url}/{prefix}index.html"
        logger.info(f"uploaded session with {len(files)} file(s) to {prefix}")
        return url

    def _put_file(self, key: str, path: Path) -> None:
        assert self._client and self._settings
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self._client.upload_file(str(path), self._settings.bucket, key, ExtraArgs={"ContentType": content_type})

    @staticmethod
    def _render_index(collage: str, originals: list[str], timelapse: str | None, expires: datetime) -> str:
        expires_text = expires.astimezone().strftime("%d/%m/%Y")
        video = (
            f'<h2>Video timelapse</h2><video src="{escape(timelapse)}" controls playsinline muted loop></video>'
            f'<a class="btn" href="{escape(timelapse)}" download>Tải video</a>'
            if timelapse
            else ""
        )
        originals_html = "".join(
            f'<a class="thumb" href="{escape(name)}" download><img src="{escape(name)}" loading="lazy" alt="Ảnh gốc {index}"></a>'
            for index, name in enumerate(originals, start=1)
        )
        originals_block = f'<h2>Ảnh gốc</h2><div class="grid">{originals_html}</div>' if originals else ""

        return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ảnh của bạn - TSL Photobooth</title>
<style>
body{{margin:0;font-family:system-ui,sans-serif;background:#f6f1f3;color:#1c1b1f;padding:16px;max-width:560px;margin-inline:auto}}
h1{{font-size:1.4rem}}h2{{font-size:1.05rem;margin:24px 0 8px}}
img,video{{width:100%;border-radius:12px;display:block;background:#ddd}}
.btn{{display:block;text-align:center;margin:12px 0;padding:14px;border-radius:12px;
background:#1c1b1f;color:#fff;text-decoration:none;font-weight:600}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}.thumb img{{aspect-ratio:3/2;object-fit:cover}}
small{{color:#666}}
</style></head><body>
<h1>Ảnh của bạn đã sẵn sàng</h1>
<img src="{escape(collage)}" alt="Ảnh ghép">
<a class="btn" href="{escape(collage)}" download>Tải ảnh ghép</a>
{video}
{originals_block}
<p><small>Liên kết có hiệu lực đến hết ngày {expires_text}. Hãy tải về trước khi hết hạn.</small></p>
</body></html>"""

    def usage(self, max_age_seconds: float = 60.0) -> dict:
        """Objects and bytes stored below ``sessions/`` (cached for a minute, listing is billed per call)."""
        if not (self._client and self._settings):
            return {"available": False, "objects": 0, "bytes": 0, "bucket": None, "public_url": None}
        now = time.monotonic()
        cached = getattr(self, "_usage_cache", None)
        if cached and now - cached[0] < max_age_seconds:
            return cached[1]
        objects = 0
        size = 0
        try:
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self._settings.bucket, Prefix=SESSIONS_PREFIX):
                for obj in page.get("Contents", []):
                    objects += 1
                    size += int(obj.get("Size", 0))
            result = {"available": True, "objects": objects, "bytes": size, "bucket": self._settings.bucket, "public_url": self._settings.public_url}
        except Exception as exc:
            logger.warning(f"could not read cloud usage: {exc}")
            result = {"available": False, "objects": 0, "bytes": 0, "bucket": self._settings.bucket, "public_url": self._settings.public_url}
        self._usage_cache = (now, result)
        return result

    def sweep_expired(self) -> int:
        """Delete every object older than the retention period. Returns the number of deleted objects."""
        if not (self._client and self._settings):
            return 0

        cutoff = datetime.now(UTC) - timedelta(days=appconfig.framebooth.digital_delivery_retention_days)
        expired: list[dict[str, str]] = []
        try:
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self._settings.bucket, Prefix=SESSIONS_PREFIX):
                expired += [{"Key": obj["Key"]} for obj in page.get("Contents", []) if obj["LastModified"] < cutoff]

            for start in range(0, len(expired), 1000):
                self._client.delete_objects(
                    Bucket=self._settings.bucket,
                    Delete={"Objects": expired[start : start + 1000], "Quiet": True},
                )
        except Exception as exc:
            logger.warning(f"cloud retention sweep failed: {exc}")
            return 0

        if expired:
            logger.info(f"cloud retention sweep deleted {len(expired)} object(s) older than {cutoff:%Y-%m-%d}")
        return len(expired)
