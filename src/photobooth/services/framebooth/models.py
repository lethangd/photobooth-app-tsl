from pathlib import Path

from pydantic import BaseModel


class FrameSlot(BaseModel):
    """A rectangular placeholder inside a frame image where a capture is pasted."""

    x: int
    y: int
    width: int
    height: int


class FrameTemplate(BaseModel):
    """A decorative frame with one or more auto-detected photo slots."""

    id: str
    frame_type: str
    name: str
    file: Path
    width: int
    height: int
    placeholder: str
    slots: list[FrameSlot]
