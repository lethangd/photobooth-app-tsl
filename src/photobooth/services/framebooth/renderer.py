"""Composite the selected captures into a framed collage image."""

from io import BytesIO
from pathlib import Path

import numpy as np
from fastapi.responses import StreamingResponse
from PIL import Image, ImageOps

from .filters import apply_filter
from .models import FrameTemplate


def build_frame_alpha(template: FrameTemplate) -> Image.Image:
    """Load the frame image and punch transparent holes where the placeholder
    rectangles are, so the pasted captures show through."""
    frame = Image.open(template.file).convert("RGBA")
    rgb = np.asarray(frame.convert("RGB"))
    if template.placeholder == "white":
        placeholder_pixels = (rgb[:, :, 0] > 238) & (rgb[:, :, 1] > 238) & (rgb[:, :, 2] > 238)
    else:
        placeholder_pixels = (rgb[:, :, 0] < 45) & (rgb[:, :, 1] < 45) & (rgb[:, :, 2] < 45)

    alpha = np.full((template.height, template.width), 255, dtype=np.uint8)
    for slot in template.slots:
        y2 = slot.y + slot.height
        x2 = slot.x + slot.width
        alpha[slot.y : y2, slot.x : x2][placeholder_pixels[slot.y : y2, slot.x : x2]] = 0

    frame.putalpha(Image.fromarray(alpha, mode="L"))
    return frame


def render_collage_image(template: FrameTemplate, capture_paths: list[Path], filter_id: str) -> Image.Image:
    canvas = Image.new("RGBA", (template.width, template.height), (255, 255, 255, 255))

    for capture_path, slot in zip(capture_paths, template.slots, strict=True):
        with Image.open(capture_path) as image:
            image = ImageOps.exif_transpose(image)
            image = apply_filter(image, filter_id)
            fitted = ImageOps.fit(image, (slot.width, slot.height), method=Image.Resampling.BICUBIC).convert("RGBA")
            canvas.paste(fitted, (slot.x, slot.y), fitted)

    frame = build_frame_alpha(template)
    canvas.paste(frame, (0, 0), frame)
    return canvas.convert("RGB")


def render_preview_response(image: Image.Image) -> StreamingResponse:
    image = image.copy()
    image.thumbnail((900, 900), Image.Resampling.LANCZOS)
    output = BytesIO()
    image.save(output, format="JPEG", quality=88)
    output.seek(0)
    return StreamingResponse(output, media_type="image/jpeg")


def apply_overlay(image: Image.Image, overlay_png: str) -> Image.Image:
    """Lay the guest's decoration (stickers, text, doodles; a transparent PNG as data URL or base64) over the collage."""
    import base64  # noqa: PLC0415

    data = overlay_png.split(",", 1)[1] if overlay_png.startswith("data:") else overlay_png
    try:
        with Image.open(BytesIO(base64.b64decode(data))) as decoded:
            overlay = decoded.convert("RGBA").resize(image.size, Image.Resampling.LANCZOS)
    except Exception:
        return image  # a broken decoration must never stop the print
    base = image.convert("RGBA")
    base.alpha_composite(overlay)
    return base.convert("RGB")
