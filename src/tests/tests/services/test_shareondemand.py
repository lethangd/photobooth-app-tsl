import logging
from collections.abc import Generator
from uuid import uuid4

import pytest
import requests

from photobooth.appconfig import appconfig
from photobooth.container import Container, container
from photobooth.database.models import Mediaitem

logger = logging.getLogger(name=None)

r = requests.get(appconfig.shareondemand.baseurl.rstrip("/") + "/api.php", params={"action": "version"}, allow_redirects=False)
is_valid_service = False
try:
    is_valid_service = "type" in list(r.json().keys())
except Exception:
    is_valid_service = False

if not is_valid_service:
    logger.warning(f"no webservice found, skipping tests {appconfig.shareondemand.baseurl}")
    pytest.skip("no webservice found, skipping tests", allow_module_level=True)


@pytest.fixture(scope="module")
def _container() -> Generator[Container, None, None]:
    appconfig.shareondemand.enabled = True

    container.start()
    yield container
    container.stop()


# @pytest.fixture()
@pytest.fixture(params=["image", "collage", "animation", "video"])
def _mediaitem(request, _container: Container) -> Generator[Mediaitem, None, None]:
    _container.processing_service.trigger_action(request.param)
    container.processing_service.wait_until_job_finished()
    yield _container.mediacollection_service.get_item_latest()


def test_shareondemand_landingpage_valid():
    # ensure that the landingpage is available - this is a default configured address and helps the user during setup of a booth
    r = requests.get("https://photobooth-app.org/extras/shareondemand-landing/")
    assert r.ok


def test_shareondemand_urls_valid():
    """test some common actions on url"""

    # /api.php
    r = requests.get(appconfig.shareondemand.baseurl + "/api.php")
    logger.warning(appconfig.shareondemand.baseurl)
    assert r.json()  # ensure we can decode every answer as json
    assert r.status_code == 400

    # info action
    r = requests.get(appconfig.shareondemand.baseurl + "/api.php", params={"action": "version"})
    logger.info(f"{r.text=}")
    assert r.json()  # ensure we can decode every answer as json
    assert r.status_code == 200

    # invalid action
    r = requests.get(appconfig.shareondemand.baseurl + "/api.php", params={"action": "nonexistentaction"})
    logger.info(f"{r.text=}")
    assert r.json()  # ensure we can decode every answer as json
    assert r.status_code == 400

    # invalid apikey
    r = requests.post(
        appconfig.shareondemand.baseurl + "/api.php",
        files=None,
        data={
            "action": "upload",
            "apikey": "wrongapikeyprovided",
            "id": "invalididdoesntmatteranyway",
        },
    )
    logger.info(f"{r.text=}")
    assert r.json()  # ensure we can decode every answer as json
    assert r.status_code == 500


def test_shareondemand_download_all_mediaitem_types(_mediaitem: Mediaitem):
    """start service and try to download an image"""

    logger.info(f"check to download {_mediaitem.id=}, {_mediaitem.media_type=}")
    r = requests.get(
        appconfig.shareondemand.baseurl + "/api.php",
        params={"action": "download", "id": str(_mediaitem.id)},
    )

    # valid status code
    assert r.status_code == 200

    # check we received the same file via php api
    with open(_mediaitem.processed, "rb") as f:
        assert r.content == f.read()


def test_shareondemand_download_nonexistant_image(_container: Container):
    """start service and try to download an image that does not exist"""

    r = requests.get(
        appconfig.shareondemand.baseurl + "/api.php",
        params={"action": "download", "id": uuid4().hex},
    )

    # valid status code is 500 because image not existing.
    assert r.status_code == 500
    assert r.json()


def test_shareondemand_reconnect():
    """start service and try service to reconnect if line is temporarily down"""
