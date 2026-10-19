from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from photobooth.services.framebooth.letterbox import content_box, trim_file


def _pillarboxed(width=1920, height=1080, picture_width=1620) -> Image.Image:
    """A 3:2 picture inside a 16:9 frame, like a Sony in photo mode over HDMI."""
    image = Image.new("RGB", (width, height), "black")
    left = (width - picture_width) // 2
    ImageDraw.Draw(image).rectangle([left, 0, left + picture_width - 1, height - 1], fill=(120, 140, 160))
    return image


def test_black_side_bars_are_cut(tmp_path: Path):
    path = tmp_path / "still.jpg"
    _pillarboxed().save(path, quality=95)
    assert trim_file(path)
    with Image.open(path) as image:
        assert abs(image.width - 1620) <= 4 and image.height == 1080


def test_normal_photos_are_left_alone(tmp_path: Path):
    path = tmp_path / "still.jpg"
    image = Image.new("RGB", (1920, 1080), (90, 90, 90))
    ImageDraw.Draw(image).rectangle([0, 0, 120, 1079], fill="black")  # dark area on one side only: not a bar
    image.save(path)
    assert not trim_file(path)
    assert content_box(np.zeros((90, 160, 3), dtype=np.uint8)) is None  # all black: untouched
