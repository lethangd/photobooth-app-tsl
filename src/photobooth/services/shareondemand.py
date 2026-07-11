"""
https://photobooth-app.org/setup/configuration/qrshareservice/
"""

import json
import logging
import time
from typing import Any
from urllib.parse import quote
from uuid import UUID

import requests

from ..appconfig import appconfig
from ..utils.stoppablethread import StoppableThread
from .base import BaseService
from .collection import MediacollectionService

logger = logging.getLogger(__name__)

API_PHP = "api.php"


class ShareOnDemandService(BaseService):
    def __init__(self, mediacollection_service: MediacollectionService):
        super().__init__()

        # objects
        self._mediacollection_service: MediacollectionService = mediacollection_service
        self._worker_thread: StoppableThread | None = None

        self.shareservice_api_php_url = appconfig.shareondemand.baseurl.rstrip("/") + "/" + API_PHP

    def start(self):
        super().start()

        if not appconfig.shareondemand.enabled:
            logger.info("ShareOnDemand service disabled, not starting.")
            super().disabled()
            return

        self._worker_thread = StoppableThread(name="ShareOnDemand_worker", target=self._worker_fun, daemon=True)
        self._worker_thread.start()

        logger.debug(f"{self.__class__.__name__} started using endpoint baseurl {appconfig.shareondemand.baseurl}.")

        super().started()

    def stop(self):
        super().stop()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.stop()
            self._worker_thread.join()

        super().stopped()

    def get_share_link(self, identifier: UUID, filename: str) -> list[str]:
        logger.debug(f"generating qr share links for {identifier} {filename}")

        out_links: list[str] = []

        # qr share service with dl.php:
        if appconfig.shareondemand.enabled:
            # this is to the index.html displaying the portal
            download_portal_url = f"{appconfig.shareondemand.baseurl.rstrip('/')}/#/?url="
            # this delivers the actual file (no html around).
            mediaitem_url = f"{appconfig.shareondemand.baseurl.rstrip('/')}/{API_PHP}?action=download&id={str(identifier)}"

            out_links.append(download_portal_url + quote(mediaitem_url, safe=""))

        return out_links

    def _worker_fun(self):
        assert self._worker_thread

        logger.info("starting ShareOnDemand worker_thread")

        while not self._worker_thread.stopped():
            payload = {"action": "upload_queue", "apikey": appconfig.shareondemand.apikey}
            r = None

            try:
                r = requests.post(
                    self.shareservice_api_php_url,
                    data=payload,
                    stream=True,
                    timeout=8,
                    allow_redirects=False,
                )
                r.raise_for_status()

                logger.info("successfully connected to the api")

            except requests.exceptions.ReadTimeout as exc:
                logger.warning(f"error connecting to service: {exc}")
                time.sleep(10)
                continue  # try again after wait time
            except requests.HTTPError:
                try:
                    err = r.json() if r is not None else "no further details"
                except json.JSONDecodeError:
                    err = "cannot decode server's answer"
                except Exception as exc:
                    err = f"unknown exception {exc}"

                logger.error(f"server error code {r.status_code if r is not None else '?'} for req URL {r.url if r is not None else '?'}: {err}")
                time.sleep(10)
                continue
            except Exception as exc:
                logger.error(f"unknown error occured: {exc}")
                time.sleep(10)
                continue  # try again after wait time

            if r.encoding is None:
                r.encoding = "utf-8"

            iterator = r.iter_lines(chunk_size=24, decode_unicode=True)

            while not self._worker_thread.stopped():
                try:
                    line = next(iterator)
                except StopIteration:
                    logger.debug("dl.php script finished after some time. stopiteration issued-reconnect")
                    break
                except Exception as exc:
                    logger.warning(f"encountered shareservice connection issue. retrying. error: {exc}")
                    break

                # filter out keep-alive new lines
                if line:
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

                    if decoded_line.get("id", None):  # and decoded_line.get("status", None):
                        # valid job check whether pending and upload
                        logger.info(f"got share upload job, {decoded_line}")

                        # set the file to be uploaded
                        request_upload_file = {}
                        try:
                            mediaitem_to_upload = self._mediacollection_service.get_item(UUID(decoded_line["id"]))
                            logger.info(f"found mediaitem to upload: {mediaitem_to_upload}")
                        except Exception as exc:
                            logger.error(f"mediaitem not found, error: {exc}")
                            logger.info("sending upload request to dl.php anyway to signal failure")
                        else:
                            logger.info(f"mediaitem to upload: {mediaitem_to_upload}")
                            request_upload_file = {"upload_file": open(mediaitem_to_upload.processed, "rb")}

                        ## send request
                        start_time = time.time()

                        try:
                            r = requests.post(
                                self.shareservice_api_php_url,
                                files=request_upload_file,  # type: ignore
                                data={
                                    "action": "upload",
                                    "apikey": appconfig.shareondemand.apikey,
                                    "id": decoded_line["id"],
                                },
                                timeout=9,
                                allow_redirects=False,
                            )
                        except Exception as exc:
                            logger.warning(f"upload failed, err: {exc}")
                            # try again?

                        else:
                            logger.debug(f"response from remote server: {r.text}")
                            logger.debug(f"-- request took: {round((time.time() - start_time), 2)}s")
                    elif decoded_line.get("ping", None):
                        pass
                    else:
                        logger.error(f"invalid queue line, ignore: {line}")

                # if a keepalive message is issued, we can check here also regularly for exit condition set
                if self._worker_thread.stopped():
                    logger.debug("stop workerthread requested")
                    break

            if not self._worker_thread.stopped():
                # usually dl.php finishes after several minutes and the client needs to reconnect again.
                logger.info("restarting loop wait 1 second")
                time.sleep(1)

        logger.info("leaving shareservice workerthread")
