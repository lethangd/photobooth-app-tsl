import logging
import os
import tempfile
from collections.abc import Generator
from pathlib import Path

# keep the admin password / staff PIN written by tests away from the real .env (set before the app is imported)
os.environ["PHOTOBOOTH_SECRETS_FILE"] = str(Path(tempfile.gettempdir(), f"photobooth-test-{os.getpid()}.env"))
os.environ["AUTH_TOKEN_SECRET"] = "test-token-secret-0123456789abcdef0123456789"  # stable across the per-test reset of the secrets file

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from photobooth.appconfig import appconfig  # noqa: E402
from photobooth.application import app  # noqa: E402
from photobooth.container import container  # noqa: E402
from photobooth.database.database import create_db_and_tables  # noqa: E402
from photobooth.services.collection import MediacollectionService  # noqa: E402
from tests.tests.util import dummy_mediaitem  # noqa: E402

logger = logging.getLogger(name=None)


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app=app, base_url="http://test/api/") as client:
        if not container.is_started():
            container.start()

        yield client

        assert container.is_started(), "container need to be in started state until the very end! otherwise it might reveal issues with the tests."


@pytest.fixture
def client_authenticated(client: TestClient) -> Generator[TestClient, None, None]:
    response = client.post("/admin/auth/token", data={"username": "admin", "password": "0000"})
    token = response.json()["access_token"]
    client.headers = {"Authorization": f"Bearer {token}"}
    yield client


@pytest.fixture(scope="function", autouse=True)
def global_function_setup1():
    mcs = MediacollectionService()

    create = False
    try:
        latest = mcs.get_item_latest()

        if latest.media_type != "image":
            create = True
    except FileNotFoundError:
        create = True

    if create:
        logger.info("no mediaitem in collection, creating one image")

        dummy_item = dummy_mediaitem()

        mcs.add_item(dummy_item)

    yield


@pytest.fixture(scope="function", autouse=True)
def global_function_setup2():
    appconfig.reset_defaults()
    Path(os.environ["PHOTOBOOTH_SECRETS_FILE"]).unlink(missing_ok=True)  # back to default password "0000" / PIN "1234"

    appconfig.actions.image[0].jobcontrol.countdown_capture = 0.2
    appconfig.actions.collage[0].jobcontrol.countdown_capture = 0.2
    appconfig.actions.collage[0].jobcontrol.countdown_capture_second_following = 0.2
    appconfig.actions.collage[0].jobcontrol.approve_autoconfirm_timeout = 0.5

    yield


@pytest.fixture(scope="session", autouse=True)
def session_setup1():
    create_db_and_tables()

    yield
