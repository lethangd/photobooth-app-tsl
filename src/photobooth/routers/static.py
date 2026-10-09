import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, RedirectResponse, Response

from .. import USERDATA_PATH

logger = logging.getLogger(__name__)
static_router = APIRouter(tags=["static"])

_FRONTEND_DIR = Path(__file__).parent.parent.parent.joinpath("web/frontend").resolve()


@static_router.get("/private.css")
def ui_private_css():
    """
    if private.css exists return the file content, otherwise send empty response to avoid 404
    """
    path = Path(USERDATA_PATH, "private.css")
    headers = {"Cache-Control": "no-store, no-cache, must-revalidate"}
    if not path.is_file():
        return Response("/* placeholder. create private.css in userdata folder to customize css */", headers=headers)
    else:
        return FileResponse(path=path, headers=headers)


@static_router.get("/")
def index():
    """Serve the kiosk (Framebooth) SPA. Built from frontend-kiosk/ into web/frontend/framebooth.html."""
    headers = {"Cache-Control": "no-cache"}
    return FileResponse(path=_FRONTEND_DIR.joinpath("framebooth.html"), headers=headers)


@static_router.get("/legacy")
def legacy_index():
    """Serve the previous single-file kiosk. Kept temporarily to compare against the Vue rewrite."""
    headers = {"Cache-Control": "no-cache"}
    return FileResponse(path=_FRONTEND_DIR.joinpath("framebooth-legacy.html"), headers=headers)


@static_router.get("/classic")
def classic_index():
    """Serve the original SPA index.html with forced revalidation."""
    headers = {"Cache-Control": "no-cache"}
    return FileResponse(path=_FRONTEND_DIR.joinpath("index.html"), headers=headers)


@static_router.get("/admin")
def admin_index():
    """Admin dashboard SPA (built from frontend-kiosk/admin.html). Falls back to the classic admin if it is not built."""
    admin_html = _FRONTEND_DIR.joinpath("admin.html")
    if not admin_html.is_file():
        return RedirectResponse("/classic#/admin")
    return FileResponse(path=admin_html, headers={"Cache-Control": "no-cache"})
