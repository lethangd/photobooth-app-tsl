"""
AppConfig class providing central config

"""

from platform import node

from pydantic import BaseModel, ConfigDict, Field

hostname = node() if node() != "" else "localhost"


class GroupShareOnDemand(BaseModel):
    model_config = ConfigDict(title="Share on Demand")

    enabled: bool = Field(
        default=False,
        description="Enable on demand share service using QR codes. To enable the URL needs to be configured and the api.php script setup properly.",
    )
    baseurl: str = Field(
        default="https://photobooth-app.org/extras/shareondemand-landing/",
        description="URL to the folder on a webspace where the api.php is located. The default is a landingpage with further instructions how to setup and needs to be changed.",
    )
    apikey: str = Field(
        default="changedefault!",
        description="Key to secure the api.php script. Set the key in api.php script to same value. Only if the keys match on both ends, the service can operate.",
    )
