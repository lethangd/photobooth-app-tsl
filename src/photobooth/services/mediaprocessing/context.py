from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt
from PIL import Image


@dataclass
class ImageContext:
    image: Image.Image
    preview: bool = False


@dataclass
class CollageContext:
    canvas: Image.Image
    images: list[Image.Image]


@dataclass
class MulticameraContext:
    images: list[Image.Image]
    good_features_to_track: npt.NDArray[np.float32] | None = None

    relative_offsets: list[tuple[int, int]] = field(default_factory=list)
