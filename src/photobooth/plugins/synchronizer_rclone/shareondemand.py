"""
https://photobooth-app.org/setup/configuration/qrshareservice/
"""

import json
import logging
import tempfile
import time
from importlib import resources
from pathlib import Path
from threading import Event
from typing import Any
from urllib.parse import quote
from uuid import UUID

import requests
from rclone_api.api import RcloneApi

from ...services.mediacollection.database import Database
from ...utils.stoppablethread import StoppableThread

logger = logging.getLogger(__name__)

API_PHP = "api.php"


class ShareOnDemandService:
    def __init__(self, rclone: RcloneApi, remote_name: str, remote_subdir: str, baseurl: str, apikey: str):

        # objects

        self._mediacollection_db: Database = Database()
        self._worker_thread: StoppableThread | None = None

        self.rclone: RcloneApi = rclone
        self.remote_name: str = remote_name
        self.remote_subdir: str = remote_subdir
        self.baseurl: str = baseurl
        self.apikey: str = apikey

        self.shareservice_api_php_url = baseurl.rstrip("/") + "/" + API_PHP
        self.operational_flag = Event()

    def start(self):
        self.operational_flag.clear()

        self._worker_thread = StoppableThread(name="ShareOnDemand_worker", target=self._worker_fun, daemon=True)
        self._worker_thread.start()

        logger.debug(f"{self.__class__.__name__} started using endpoint baseurl {self.baseurl}.")

    def stop(self):
        self.operational_flag.clear()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.stop()
            self._worker_thread.join()

    def _copy_frontend_to_remote(self):
        assert self.rclone

        api_source_path = Path(str(resources.files("web").joinpath("shareondemand/api.php")))
        assert api_source_path.is_file()

        # replace the default apikey by the chosen one
        content = api_source_path.read_text(encoding="utf-8")
        patched = content.replace("changedefault!", self.apikey, 1)  # count=1, only replace first occurence, keyword since 3.13 only

        # write patched version to a temp file
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp:
            tmp.write(patched)
            tmp_path = Path(tmp.name)

        logger.info(f"update api to {self.remote_name}{self.remote_subdir}")

        # add to queue for later upload.
        # this way if no internet the startup is not causing issues preventing the complete app from startup
        self.rclone.copyfile(
            tmp_path.parent.as_posix(),
            tmp_path.name,
            self.remote_name,
            Path(self.remote_subdir, api_source_path.name).as_posix(),
        )

        indexhtml_source_path = Path(str(resources.files("web").joinpath("sharepage/index.html")))
        assert indexhtml_source_path.is_file()

        self.rclone.copyfile(
            indexhtml_source_path.parent.as_posix(),
            indexhtml_source_path.name,
            self.remote_name,
            Path(self.remote_subdir, indexhtml_source_path.name).as_posix(),
        )

    def get_share_link(self, identifier: UUID) -> str:
        logger.debug(f"generating shareondemand qr links for {identifier}")

        # qr share service with api.php:
        # this is to the index.html displaying the portal
        download_portal_url = f"{self.baseurl.rstrip('/')}/#/?url="
        # this delivers the actual file (no html around).
        mediaitem_url = f"{self.baseurl.rstrip('/')}/{API_PHP}?action=download&id={str(identifier)}"

        return download_portal_url + quote(mediaitem_url, safe="")

    def _worker_fun(self):
        assert self._worker_thread

        logger.info("starting ShareOnDemand worker_thread")
        self._copy_frontend_to_remote()

        self.operational_flag.set()

        # outer while loop: connect to uploadqueue-stream
        while not self._worker_thread.stopped():
            payload = {"action": "upload_queue", "apikey": self.apikey}
            r_stream = None

            try:
                r_stream = requests.post(
                    self.shareservice_api_php_url,
                    data=payload,
                    stream=True,
                    timeout=8,
                    allow_redirects=False,
                )

                r_stream.raise_for_status()

                logger.info("successfully connected to the api")

            except requests.exceptions.ReadTimeout as exc:
                logger.warning(f"error connecting to service: {exc}")
                time.sleep(10)
                continue  # try again after wait time
            except requests.HTTPError:
                try:
                    err = r_stream.json() if r_stream is not None else "no further details"
                except json.JSONDecodeError:
                    err = "cannot decode server's answer"
                except Exception as exc:
                    err = f"unknown exception {exc}"

                logger.error(
                    f"server error code {r_stream.status_code if r_stream is not None else '?'} "
                    f"for req URL {r_stream.url if r_stream is not None else '?'}: {err}"
                )
                time.sleep(10)
                continue
            except Exception as exc:
                logger.error(f"unknown error occured: {exc}")
                time.sleep(10)
                continue  # try again after wait time

            if r_stream.encoding is None:
                r_stream.encoding = "utf-8"

            stream_it = r_stream.iter_lines(chunk_size=1, decode_unicode=True)

            # inner while loop: check stream for upload job requested
            while not self._worker_thread.stopped():
                try:
                    line = next(stream_it)
                except StopIteration:
                    logger.debug("api.php script finished after some time. stopiteration issued-reconnect")
                    break
                except Exception as exc:
                    logger.warning(f"encountered shareservice connection issue. retrying. error: {exc}")
                    break

                # filter out keep-alive new lines

                try:
                    # if webserver not correctly setup, decoding might fail. catch exception mostly to inform user to debug
                    decoded_line: dict[str, Any] = json.loads(line)
                except json.JSONDecodeError as exc:
                    logger.error(
                        f"webserver response from webserver malformed. please check qr shareservice url, "
                        f"webserver setup and webserver's logs. error: {exc}"
                        f"URL trying to connect is {self.shareservice_api_php_url}"
                    )
                    time.sleep(5)  # if url is wrong just slow down to not reconnect every second.
                    break

                upload_id: str | None = decoded_line.get("id", None)
                if upload_id:
                    # valid job check whether pending and upload
                    logger.debug(f"got upload job, id {upload_id}")

                    # protect the following path - to ensure it would complete or gets stopped before accepting.
                    if self._worker_thread.stopped():
                        break

                    # ACK senden
                    requests.post(
                        self.shareservice_api_php_url,
                        data={"action": "accept", "apikey": self.apikey, "id": upload_id},
                        timeout=5,
                    )

                    # set the file to be uploaded
                    request_upload_file = {}
                    try:
                        mediaitem_to_upload = self._mediacollection_db.get_item(UUID(upload_id))
                    except Exception as exc:
                        logger.error(f"mediaitem not found, error: {exc}")
                        logger.info("sending upload request to api.php anyway to signal failure")
                    else:
                        logger.info(f"uploading {mediaitem_to_upload}")
                        request_upload_file = {"upload_file": open(mediaitem_to_upload.processed, "rb")}

                    ## send request
                    start_time = time.time()
                    r_upload = None

                    try:
                        r_upload = requests.post(
                            self.shareservice_api_php_url,
                            files=request_upload_file,  # type: ignore
                            data={"action": "upload", "apikey": self.apikey, "id": upload_id},
                            timeout=9,
                            allow_redirects=False,
                        )
                        r_upload.raise_for_status()

                    except requests.HTTPError as exc:
                        assert exc.response
                        logger.warning(exc)
                        logger.warning(f"upload failed {exc.response.status_code}: {exc.response.text}")
                        # try again?
                    except Exception as exc:
                        logger.warning(f"upload failed, err: {exc}")
                        # try again?

                    else:
                        logger.debug(f"response from remote server: {r_upload.text}")
                        logger.debug(f"-- request took: {round((time.time() - start_time), 2)}s")
                elif decoded_line.get("ping", None):
                    pass
                else:
                    logger.error(f"invalid queue line, ignore: {line}")

            if not self._worker_thread.stopped():
                # usually api.php finishes after several minutes and the client needs to reconnect again.
                logger.info("restarting loop wait 1 second")
                time.sleep(1)

        logger.info("leaving shareservice workerthread")
