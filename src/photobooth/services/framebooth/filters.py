"""Color filters offered to the guest.

The list of filters (id / name / css_filter) is configured in
``appconfig.framebooth.filters`` so it can be edited from the Admin config page.
Each ``id`` needs a matching PIL implementation in :func:`apply_filter`; unknown
ids fall through to the unmodified image (same as ``natural``).
"""

from collections.abc import Callable

from PIL import Image, ImageEnhance, ImageOps

from ...appconfig import appconfig
from ...services.config.groups.framebooth import FramebootFilterDefinition


def _curve(channel: Image.Image, transform: Callable[[float], float]) -> Image.Image:
    # PIL's point() stub mis-types the lambda argument; it is an int pixel value here.
    return channel.point(lambda value: max(0, min(255, int(transform(value)))))  # pyright: ignore[reportArgumentType]


def get_filter_ids() -> set[str]:
    return {filter_config.id for filter_config in appconfig.framebooth.filters}


def filter_to_public(filter_config: FramebootFilterDefinition) -> dict:
    return {
        "id": filter_config.id,
        "name": filter_config.name,
        "css_filter": filter_config.css_filter,
    }


def apply_filter(image: Image.Image, filter_id: str) -> Image.Image:
    image = image.convert("RGB")
    if filter_id == "vivid":
        image = ImageEnhance.Color(image).enhance(1.35)
        return ImageEnhance.Contrast(image).enhance(1.1)
    if filter_id == "warm":
        r, g, b = image.split()
        r = _curve(r, lambda value: value * 1.06 + 4)
        b = _curve(b, lambda value: value * 0.93)
        image = Image.merge("RGB", (r, g, b))
        return ImageEnhance.Color(image).enhance(1.12)
    if filter_id == "mono":
        return ImageOps.grayscale(image).convert("RGB")
    if filter_id == "film":
        r, g, b = image.split()
        r = _curve(r, lambda value: value * 1.05 + 3)
        g = _curve(g, lambda value: value * 1.02)
        b = _curve(b, lambda value: value * 0.9)
        image = Image.merge("RGB", (r, g, b))
        image = ImageEnhance.Contrast(image).enhance(1.08)
        return ImageEnhance.Color(image).enhance(0.92)
    return image
