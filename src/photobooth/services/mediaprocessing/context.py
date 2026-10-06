from dataclasses import dataclass

from PIL import Image


@dataclass
class ImageContext:
    image: Image.Image
    preview: bool = False


@dataclass
class CollageContext:
    canvas: Image.Image
    images: list[Image.Image]
