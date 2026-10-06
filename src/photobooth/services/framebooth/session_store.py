"""Short-lived storage for the captures / timelapses of the current guest.

Files live under ``tmp/framebooth/``. Entries (and their files) are dropped a
while after they were created by a background timer so an unattended kiosk does
not grow ``tmp/`` without bound.
"""

import logging
import shutil
import time
from pathlib import Path
from threading import Lock
from uuid import UUID, uuid4

from ... import TMP_PATH
from ...utils.repeatedtimer import RepeatedTimer

logger = logging.getLogger(__name__)

CAPTURE_DIR = Path(TMP_PATH) / "framebooth"
TIMELAPSE_DIR = CAPTURE_DIR / "timelapse"

# a kiosk session lasts a few minutes; keep the files noticeably longer for
# safety (retry, slow guest) and then discard them.
_ENTRY_TTL_SECONDS = 30 * 60
_CLEANUP_INTERVAL_SECONDS = 5 * 60


class SessionStore:
    def __init__(
        self,
        entry_ttl_seconds: float = _ENTRY_TTL_SECONDS,
        cleanup_interval_seconds: float = _CLEANUP_INTERVAL_SECONDS,
    ):
        self._entry_ttl_seconds = entry_ttl_seconds
        self._lock = Lock()
        self._captures: dict[UUID, tuple[Path, float]] = {}
        self._timelapses: dict[UUID, tuple[Path, float]] = {}
        self._cleanup_timer = RepeatedTimer(cleanup_interval_seconds, self.cleanup)
        self._cleanup_started = False

    def _ensure_cleanup_running(self) -> None:
        if not self._cleanup_started:
            self._cleanup_started = True
            self._cleanup_timer.start()

    # -- captures --------------------------------------------------------
    def add_capture(self, source: Path) -> tuple[UUID, Path]:
        CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
        capture_id = uuid4()
        destination = CAPTURE_DIR / f"{capture_id}{source.suffix}"
        shutil.copy2(source, destination)
        with self._lock:
            self._captures[capture_id] = (destination, time.monotonic())
        self._ensure_cleanup_running()
        return capture_id, destination

    def get_capture(self, capture_id: UUID) -> Path | None:
        with self._lock:
            entry = self._captures.get(capture_id)
        if not entry:
            return None
        path, _ = entry
        return path if path.is_file() else None

    def resolve_captures(self, capture_ids: list[UUID]) -> list[Path] | None:
        """Return the file paths for the given ids, or ``None`` if any is missing."""
        paths: list[Path] = []
        for capture_id in capture_ids:
            path = self.get_capture(capture_id)
            if path is None:
                return None
            paths.append(path)
        return paths

    # -- timelapses -----------------------------------------------------
    def timelapse_dir(self) -> Path:
        TIMELAPSE_DIR.mkdir(parents=True, exist_ok=True)
        return TIMELAPSE_DIR

    def register_timelapse(self, timelapse_id: UUID, path: Path) -> None:
        with self._lock:
            self._timelapses[timelapse_id] = (path, time.monotonic())
        self._ensure_cleanup_running()

    def get_timelapse(self, timelapse_id: UUID) -> Path | None:
        with self._lock:
            entry = self._timelapses.get(timelapse_id)
        if not entry:
            return None
        path, _ = entry
        return path if path.is_file() else None

    # -- maintenance --------------------------------------------------
    def cleanup(self) -> None:
        now = time.monotonic()
        with self._lock:
            expired_captures = [key for key, (_, ts) in self._captures.items() if now - ts > self._entry_ttl_seconds]
            expired_timelapses = [key for key, (_, ts) in self._timelapses.items() if now - ts > self._entry_ttl_seconds]
            paths = [self._captures.pop(key)[0] for key in expired_captures]
            paths += [self._timelapses.pop(key)[0] for key in expired_timelapses]

        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("could not remove expired framebooth file %s: %s", path, exc)

        if paths:
            logger.info("framebooth session store removed %d expired file(s)", len(paths))

    def clear(self) -> None:
        with self._lock:
            paths = [path for path, _ in self._captures.values()] + [path for path, _ in self._timelapses.values()]
            self._captures.clear()
            self._timelapses.clear()
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


session_store = SessionStore()
