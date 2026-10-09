"""
AppConfig class providing central config

"""

from pydantic import BaseModel, ConfigDict, Field


class GroupMisc(BaseModel):
    """
    Quite advanced or experimental, usually not necessary to touch. Can change any time.
    The key signing admin logins is kept in .env (AUTH_TOKEN_SECRET), see services/credentials.py.
    """

    model_config = ConfigDict(title="Miscellaneous Config")

    cmd_shutdown: str = Field(
        default="shutdown now",
        description="Command to shutdown when requested by the app. Change it if you have custom UPS solutions that need to poweroff properly.",
    )

    cmd_reboot: str = Field(
        default="reboot",
        description="Command to reboot when requested by the app. Change it if you have custom UPS solutions that need to poweroff properly.",
    )
