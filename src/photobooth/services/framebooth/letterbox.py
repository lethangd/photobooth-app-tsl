"""Remove black bars a camera adds around its picture.

Mirrorless cameras used through an HDMI capture card (e.g. a Sony a6400 left in photo mode) send
their 3:2 image inside a 16:9 signal, with black bars left and right. Photos and the timelapse
would keep those bars; this finds the real picture and crops to it.
"""

import logging
from pathlib import Path

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

_BLACK = 18  # 0..255: darker than this counts as bar
_MIN_BAR = 0.03  # a bar must take at least 3 % of the width/height to be cut


def content_box(rgb: np.ndarray) -> tuple[int, int, int, int] | None:
    """(left, top, right, bottom) of the picture inside black bars, None when there are no bars."""
    gray = rgb.max(axis=2) if rgb.ndim == 3 else rgb
    height, width = gray.shape
    cols = np.where(gray.max(axis=0) > _BLACK)[0]
    rows = np.where(gray.max(axis=1) > _BLACK)[0]
    if not len(cols) or not len(rows):
        return None  # completely dark frame (lens cap, camera off): leave it alone
    left, right, top, bottom = int(cols[0]), int(cols[-1]) + 1, int(rows[0]), int(rows[-1]) + 1
    # only real bars: wide enough and on both sides (a dark corner of a scene is not a bar)
    side_bars = left >= width * _MIN_BAR and width - right >= width * _MIN_BAR
    top_bars = top >= height * _MIN_BAR and height - bottom >= height * _MIN_BAR
    if not side_bars:
        left, right = 0, width
    if not top_bars:
        top, bottom = 0, height
    if (left, top, right, bottom) == (0, 0, width, height):
        return None
    return left, top, right, bottom


def trim_file(path: Path) -> bool:
    """Crop black bars off a photo in place. True when something was cut."""
    try:
        with Image.open(path) as image:
            image.load()
            box = content_box(np.asarray(image.convert("RGB")))
            if box is None:
                return False
            cropped = image.crop(box)
            exif = image.info.get("exif")
        cropped.save(path, quality=95, **({"exif": exif} if exif else {}))
        logger.info(f"cropped black bars off {path.name}: {box}")
        return True
    except Exception as exc:
        logger.warning(f"could not check {path} for black bars: {exc}")
        return False
