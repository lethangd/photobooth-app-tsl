import logging
from pathlib import Path

import pytest
from PIL import Image

from photobooth.services.config.groups.actions import CollageMergeDefinition
from photobooth.services.config.models.models import PluginFilters
from photobooth.services.mediaprocessing.context import CollageContext
from photobooth.services.mediaprocessing.pipeline import Pipeline
from photobooth.services.mediaprocessing.steps.animation_collage_shared import AddPredefinedImagesStep, PostPredefinedImagesStep

logger = logging.getLogger(name=None)


def test_collage_shared():
    canvas = Image.new("RGBA", (1500, 1500), color=None)
    images: list[Image.Image] = [
        Image.open("src/tests/assets/input.jpg"),
    ]
    merge_definition = [
        CollageMergeDefinition(predefined_image=Path("src/tests/assets/input.jpg"), image_filter=PluginFilters("FilterPilgram2._1977")),
        CollageMergeDefinition(image_filter=PluginFilters("FilterPilgram2._1977")),
    ]

    context = CollageContext(canvas, images)
    steps = [
        AddPredefinedImagesStep(merge_definition),
        PostPredefinedImagesStep(merge_definition),
    ]
    pipeline = Pipeline[CollageContext](*steps)
    pipeline(context)


def test_collage_shared_wrongnumbers_runtime():
    canvas = Image.new("RGBA", (1500, 1500), color=None)
    images: list[Image.Image] = [
        Image.open("src/tests/assets/input.jpg"),
        Image.open("src/tests/assets/input.jpg"),
    ]
    merge_definition = [
        # we have two captured images and two definitions but one is already a predefined. thats bad because we should have only one captured
        CollageMergeDefinition(predefined_image=Path("src/tests/assets/input.jpg"), image_filter=PluginFilters("FilterPilgram2._1977")),
        CollageMergeDefinition(image_filter=PluginFilters("FilterPilgram2._1977")),
    ]

    context = CollageContext(canvas, images)
    steps = [
        AddPredefinedImagesStep(merge_definition),
        PostPredefinedImagesStep(merge_definition),
    ]
    pipeline = Pipeline[CollageContext](*steps)

    with pytest.raises(RuntimeError):
        pipeline(context)
