import shutil
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from PIL import Image, ImageOps
from pydantic import BaseModel, Field

from ... import PATH_PROCESSED, TMP_PATH
from ...container import container
from ...database.models import Mediaitem
from ...utils.helper import filename_str_time

router = APIRouter(prefix="/framebooth", tags=["framebooth"])

FRAME_DIR = Path(__file__).resolve().parents[2] / "frame"
CAPTURE_DIR = Path(TMP_PATH) / "framebooth"


class FrameSlot(BaseModel):
    x: int
    y: int
    width: int
    height: int


class FrameTemplate(BaseModel):
    id: str
    frame_type: str
    name: str
    file: Path
    width: int
    height: int
    slots: list[FrameSlot]


class RenderRequest(BaseModel):
    template_id: str
    capture_ids: list[UUID] = Field(min_length=1)


CAPTURES: dict[UUID, Path] = {}

TEMPLATES: dict[str, FrameTemplate] = {
    "filmstrip_2": FrameTemplate(
        id="filmstrip_2",
        frame_type="2",
        name="Filmstrip 2 anh",
        file=FRAME_DIR / "0152c8b13c33b49353443a8c63da25a2.jpg",
        width=675,
        height=1200,
        slots=[
            FrameSlot(x=145, y=78, width=384, height=512),
            FrameSlot(x=146, y=604, width=385, height=511),
        ],
    ),
    "comic_3": FrameTemplate(
        id="comic_3",
        frame_type="3",
        name="Comic 3 anh",
        file=FRAME_DIR / "a52cca7a877f77fbcabb7c087db810aa.jpg",
        width=736,
        height=1308,
        slots=[
            FrameSlot(x=58, y=92, width=622, height=407),
            FrameSlot(x=60, y=541, width=613, height=414),
            FrameSlot(x=57, y=998, width=620, height=310),
        ],
    ),
    "grid_4": FrameTemplate(
        id="grid_4",
        frame_type="4",
        name="Grid 4 anh",
        file=FRAME_DIR / "37e7ede5caee4bf282d0678d4fc3c869.jpg",
        width=736,
        height=920,
        slots=[
            FrameSlot(x=31, y=28, width=323, height=404),
            FrameSlot(x=384, y=28, width=323, height=404),
            FrameSlot(x=31, y=474, width=323, height=405),
            FrameSlot(x=384, y=474, width=323, height=405),
        ],
    ),
    "comic_4": FrameTemplate(
        id="comic_4",
        frame_type="4",
        name="Comic 4 anh",
        file=FRAME_DIR / "a0da5bdc2a16a35d572214cf04029c64.jpg",
        width=736,
        height=2208,
        slots=[
            FrameSlot(x=61, y=91, width=613, height=405),
            FrameSlot(x=58, y=541, width=621, height=409),
            FrameSlot(x=60, y=991, width=613, height=410),
            FrameSlot(x=57, y=1447, width=620, height=407),
        ],
    ),
}


def _template_to_public(template: FrameTemplate) -> dict:
    return {
        "id": template.id,
        "frame_type": template.frame_type,
        "name": template.name,
        "width": template.width,
        "height": template.height,
        "slot_count": len(template.slots),
        "preview_url": f"/api/framebooth/templates/{template.id}/preview",
    }


@router.get("/config")
def api_get_framebooth_config():
    frame_types = []
    for slot_count in (2, 3, 4):
        templates = [_template_to_public(template) for template in TEMPLATES.values() if template.frame_type == str(slot_count)]
        frame_types.append(
            {
                "slot_count": slot_count,
                "shots_to_take": slot_count + 2,
                "templates": templates,
            }
        )

    return {"countdown_seconds": 10, "frame_types": frame_types}


@router.get("/templates/{template_id}/preview")
def api_get_template_preview(template_id: str):
    template = TEMPLATES.get(template_id)
    if not template:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "frame template not found")

    return FileResponse(template.file)


@router.post("/capture")
def api_capture_photo():
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        captured = container.acquisition_service.wait_for_still_file()
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"capture failed: {exc}") from exc

    capture_id = uuid4()
    destination = CAPTURE_DIR / f"{capture_id}{captured.suffix}"
    shutil.copy2(captured, destination)
    CAPTURES[capture_id] = destination

    return {
        "id": str(capture_id),
        "preview_url": f"/api/framebooth/captures/{capture_id}",
    }


@router.get("/captures/{capture_id}")
def api_get_capture(capture_id: UUID):
    path = CAPTURES.get(capture_id)
    if not path or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "capture not found")

    return FileResponse(path)


@router.post("/render")
def api_render_collage(request: RenderRequest):
    template = TEMPLATES.get(request.template_id)
    if not template:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "frame template not found")

    if len(request.capture_ids) != len(template.slots):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"template requires {len(template.slots)} selected captures")

    capture_paths = []
    for capture_id in request.capture_ids:
        path = CAPTURES.get(capture_id)
        if not path or not path.is_file():
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"capture {capture_id} not found")
        capture_paths.append(path)

    canvas = Image.new("RGBA", (template.width, template.height), (255, 255, 255, 255))
    for capture_path, slot in zip(capture_paths, template.slots, strict=True):
        with Image.open(capture_path) as image:
            image = ImageOps.exif_transpose(image)
            fitted = ImageOps.fit(image, (slot.width, slot.height), method=Image.Resampling.BICUBIC).convert("RGBA")
            canvas.paste(fitted, (slot.x, slot.y), fitted)

    frame = Image.open(template.file).convert("RGBA")
    frame = ImageOps.fit(frame, canvas.size, method=Image.Resampling.BICUBIC)
    alpha = frame.getchannel("A")
    pixels = frame.load()
    alpha_pixels = alpha.load()
    for y in range(frame.height):
        for x in range(frame.width):
            r, g, b, _ = pixels[x, y]
            if r > 238 and g > 238 and b > 238:
                alpha_pixels[x, y] = 0
    frame.putalpha(alpha)
    canvas.paste(frame, (0, 0), frame)

    output_path = Path(PATH_PROCESSED, Path(filename_str_time()).with_suffix(".jpg"))
    canvas.convert("RGB").save(output_path, quality=95)

    mediaitem = Mediaitem(
        id=uuid4(),
        job_identifier=uuid4(),
        media_type="collage",
        processed=output_path,
        pipeline_config={
            "framebooth": True,
            "template_id": template.id,
            "capture_ids": [str(capture_id) for capture_id in request.capture_ids],
        },
        show_in_gallery=True,
    )
    container.mediacollection_service.add_item(mediaitem)

    return {
        "id": str(mediaitem.id),
        "media_url": f"/media/full/{mediaitem.id}",
        "gallery_url": f"/gallery/mediaviewer/{mediaitem.id}",
    }
