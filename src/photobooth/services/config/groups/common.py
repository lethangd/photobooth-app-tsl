"""
AppConfig class providing central config

"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GroupCommon(BaseModel):
    """Common config for photobooth. The admin password is kept hashed in .env, see services/credentials.py."""

    model_config = ConfigDict(title="Common Config")

    logging_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="DEBUG",
        description="Log verbosity. File is writte to disc, and latest log is displayed also in UI.",
    )

    users_delete_to_recycle_dir: bool = Field(
        default=True,
        description="If enabled, the captured files are moved to the recycle directory instead permanently deleted. Accidentally deleted images can be restored by the admin manually. Please inform users about the fact that no capture is deleted, if you enable the function!",
    )
