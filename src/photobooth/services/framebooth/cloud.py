"""Cloudflare R2 delivery of the digital files (originals, collage, timelapse) of a kiosk session.

Credentials are read from environment variables, optionally preloaded from ``.env`` (see ``.env.example``)
or the older ``.env.r2`` file in the working directory (both git-ignored) so secrets never end up in
``config.json``::

    R2_ENDPOINT, R2_BUCKET, R2_PUBLIC_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY

Each session is uploaded below an unguessable prefix ``sessions/<token>/`` together with
``index.html`` (``delivery_page.html`` filled with the session) that the QR code links to: photos, a GIF
boomerang, the timelapse, a ZIP of everything, story / post images and a 15 s clip made in the guest's
browser, and a "delete my photos" button using presigned delete links. A background sweeper deletes sessions older than
``appconfig.framebooth.digital_delivery_retention_days``.
"""

import json
import logging
import mimetypes
import os
import secrets
import tempfile
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from PIL import Image, ImageOps

from ...appconfig import appconfig
from ...utils.repeatedtimer import RepeatedTimer
from ..base import BaseService

logger = logging.getLogger(__name__)

ENV_FILES = (Path(".env"), Path(".env.r2"))
SESSIONS_PREFIX = "sessions/"
SWEEP_INTERVAL_SECONDS = 60 * 60
UPLOAD_WORKERS = 4
PAGE_TEMPLATE = Path(__file__).with_name("delivery_page.html")
# SigV4 presigned URLs live at most 7 days
_MAX_PRESIGN_SECONDS = 7 * 24 * 3600


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
        for env_file in ENV_FILES:
            if not env_file.is_file():
                continue
            for line in env_file.read_text(encoding="utf-8").splitlines():
                key, sep, value = line.strip().partition("=")
                if sep and not key.startswith("#") and value.strip():
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
        startup = ThreadPoolExecutor(max_workers=1)
        startup.submit(self.sweep_expired)
        startup.submit(self._ensure_cors)

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
        boomerang_sources: list[Path] | None = None,
        session_id: str | None = None,
    ) -> str:
        """Upload one session and return the public URL of its landing page. Raises on failure."""
        assert self._client and self._settings, "cloud delivery not available"

        token = secrets.token_urlsafe(16)
        prefix = f"{SESSIONS_PREFIX}{token}/"
        config = appconfig.framebooth
        retention_days = config.digital_delivery_retention_days

        files: list[tuple[Path, str]] = [(collage, f"collage{collage.suffix}")]
        files += [(path, f"original_{index}{path.suffix}") for index, path in enumerate(originals, start=1)]
        if timelapse:
            files.append((timelapse, f"timelapse{timelapse.suffix}"))

        with tempfile.TemporaryDirectory() as tmp:
            boomerang = make_boomerang(boomerang_sources or originals, Path(tmp, "boomerang.gif"))
            if boomerang:
                files.append((boomerang, "boomerang.gif"))
            archive = Path(tmp, "anh-tsl-photobooth.zip")
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as bundle:  # jpg/webm/gif are compressed already
                for path, name in files:
                    bundle.write(path, name)
            files.append((archive, archive.name))

            with ThreadPoolExecutor(max_workers=UPLOAD_WORKERS) as pool:
                list(pool.map(lambda item: self._put_file(prefix + item[1], item[0]), files))

        names = [name for _, name in files]
        keys = [prefix + name for name in names] + [prefix + "index.html"]
        expires = datetime.now(UTC) + timedelta(days=retention_days)
        data = {
            "session": session_id or "",
            "created": datetime.now().astimezone().isoformat(timespec="seconds"),
            "expires": expires.isoformat(timespec="seconds"),
            "retention_days": retention_days,
            "collage": names[0],
            "originals": names[1 : 1 + len(originals)],
            "timelapse": f"timelapse{timelapse.suffix}" if timelapse else None,
            "boomerang": "boomerang.gif" if "boomerang.gif" in names else None,
            "zip": "anh-tsl-photobooth.zip",
            "handle": config.social_handle,
            "hashtag": config.social_hashtag,
            "delete_urls": self._presigned_deletes(keys, retention_days),
        }
        self._client.put_object(
            Bucket=self._settings.bucket,
            Key=prefix + "index.html",
            Body=render_delivery_page(data).encode("utf-8"),
            ContentType="text/html; charset=utf-8",
            CacheControl="no-store",
        )

        url = f"{self._settings.public_url}/{prefix}index.html"
        logger.info(f"uploaded session with {len(files)} file(s) to {prefix}")
        return url

    def _presigned_deletes(self, keys: list[str], retention_days: int) -> list[str]:
        """Links that let the guest delete their own files from the page (the page link is the secret)."""
        assert self._client and self._settings
        seconds = min(retention_days * 24 * 3600, _MAX_PRESIGN_SECONDS)
        try:
            return [
                self._client.generate_presigned_url("delete_object", Params={"Bucket": self._settings.bucket, "Key": key}, ExpiresIn=seconds)
                for key in keys
            ]
        except Exception as exc:
            logger.warning(f"could not presign delete links: {exc}")
            return []

    def _ensure_cors(self) -> None:
        """The delete button of the page sends DELETE requests from the public bucket domain to the S3 endpoint."""
        assert self._client and self._settings
        try:
            self._client.put_bucket_cors(
                Bucket=self._settings.bucket,
                CORSConfiguration={
                    "CORSRules": [
                        {
                            "AllowedOrigins": [self._settings.public_url],
                            "AllowedMethods": ["GET", "DELETE"],
                            "AllowedHeaders": ["*"],
                            "MaxAgeSeconds": 3600,
                        }
                    ]
                },
            )
        except Exception as exc:
            logger.warning(f"could not set bucket CORS (the 'delete my photos' button may not work): {exc}")

    def _put_file(self, key: str, path: Path) -> None:
        assert self._client and self._settings
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self._client.upload_file(str(path), self._settings.bucket, key, ExtraArgs={"ContentType": content_type})

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


def make_boomerang(sources: list[Path], output: Path, width: int = 480) -> Path | None:
    """Short looping GIF going forth and back through the photos."""
    frames = []
    for path in sources[:6]:
        try:
            with Image.open(path) as image:
                frame = ImageOps.exif_transpose(image).convert("RGB")
                frame.thumbnail((width, width * 2))
                frames.append(frame)
        except Exception as exc:
            logger.warning(f"skipping {path} in boomerang: {exc}")
    if len(frames) < 2:
        return None
    size = frames[0].size
    frames = [frame if frame.size == size else ImageOps.fit(frame, size) for frame in frames]
    sequence = frames + frames[-2:0:-1]
    paletted = [frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=200) for frame in sequence]
    paletted[0].save(output, save_all=True, append_images=paletted[1:], duration=180, loop=0, optimize=True)
    return output


def render_delivery_page(data: dict) -> str:
    # "</" must not end the inline <script> early
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return PAGE_TEMPLATE.read_text(encoding="utf-8").replace("__SESSION_DATA__", payload)
