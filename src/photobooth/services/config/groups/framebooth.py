"""
AppConfig class providing central config

Configuration for the self-service kiosk ("Framebooth") flow described in
src/photobooth/photobooth-kiosk-ux-spec.md. Values here map to the "PHẦN 4 —
CẤU HÌNH ADMIN PANEL" table of that spec and are consumed by
routers/api/framebooth.py and services/framebooth/*.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FramebootPricingTier(BaseModel):
    """Price for one frame layout (number of photo slots)."""

    model_config = ConfigDict(title="Pricing tier")

    slot_count: Literal[2, 3, 4] = Field(
        default=2,
        description="Number of photo slots (frame layout) this price applies to.",
    )
    price: int = Field(
        default=50_000,
        ge=0,
        description="Price in VND charged for this package.",
    )


class FramebootFilterDefinition(BaseModel):
    """One selectable color filter offered to the guest."""

    model_config = ConfigDict(title="Color filter")

    id: str = Field(
        default="natural",
        min_length=1,
        description="Unique identifier used by the frontend and the render API to select this filter. "
        "Must have a matching implementation in services/framebooth/filters.py.",
    )
    name: str = Field(
        default="Natural",
        description="Display name shown to the guest.",
    )
    css_filter: str = Field(
        default="none",
        description="CSS filter() value used for the instant client-side preview before the server renders the final image.",
    )


class FramebootVoucher(BaseModel):
    """A discount code for the payment screen."""

    model_config = ConfigDict(title="Voucher")

    code: str = Field(
        default="TSL-HELLO",
        pattern=r"^[A-Z0-9-]{3,20}$",
        description="Code the guest types, upper case letters, digits and '-'.",
    )
    discount_amount: int = Field(default=10_000, ge=0, description="Fixed discount in VND.")
    discount_percent: int = Field(default=0, ge=0, le=100, description="Percent discount (applied when > 0, instead of the fixed amount).")
    max_uses: int = Field(default=0, ge=0, description="How often the code can be used in total (0: unlimited).")
    valid_until: str = Field(default="", pattern=r"^(\d{4}-\d{2}-\d{2})?$", description="Last day the code works (YYYY-MM-DD), empty: no end.")
    enabled: bool = True



class GroupFramebooth(BaseModel):
    """Configure the self-service kiosk (Framebooth) flow: pricing, timings, filters."""

    model_config = ConfigDict(title="Framebooth Kiosk Configuration")

    pricing: list[FramebootPricingTier] = Field(
        default=[
            FramebootPricingTier(slot_count=2, price=50_000),
            FramebootPricingTier(slot_count=3, price=70_000),
            FramebootPricingTier(slot_count=4, price=90_000),
        ],
        description="Price per package, one entry per supported frame layout (2/3/4 photos).",
    )

    package_select_timeout_seconds: int = Field(
        default=60,
        ge=10,
        le=300,
        description="Idle time on the package-selection screen before the kiosk resets to idle (no payment taken yet, safe to reset).",
    )
    shot_buffer_count: int = Field(
        default=2,
        ge=1,
        le=3,
        description="Extra shots taken on top of the chosen layout so the guest can pick the best ones "
        "(totalShots = layout size + shot_buffer_count).",
    )
    capture_countdown_seconds: int = Field(
        default=10,
        ge=5,
        le=20,
        description="Countdown in seconds before each automatic shot during the capture sequence.",
    )
    get_ready_duration_seconds: int = Field(
        default=3,
        ge=1,
        le=15,
        description="How long the 'get ready' live-view screen is shown before the capture sequence starts automatically.",
    )

    payment_timeout_seconds: int = Field(
        default=180,
        ge=30,
        le=600,
        description="Maximum time the payment screen waits for the staff PIN before the kiosk cancels the session and returns to idle.",
    )
    payment_mock_seconds: int = Field(
        default=2,
        ge=1,
        le=30,
        description="Unused since payments are confirmed by staff PIN. Kept so existing config files still load.",
    )
    retake_price: int = Field(
        default=10_000,
        ge=0,
        description="Price in VND for each extra shot when the guest asks to retake on the photo-selection screen.",
    )
    retake_max_shots: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum number of extra shots a guest can buy in one retake.",
    )

    photo_select_warn_seconds: int = Field(
        default=45,
        ge=10,
        description="Idle time on the photo-selection screen before a warning countdown starts.",
    )
    photo_select_grace_seconds: int = Field(
        default=15,
        ge=5,
        description="Extra time given after the warning before the first N photos are auto-selected and the flow continues.",
    )

    filter_select_warn_seconds: int = Field(
        default=45,
        ge=10,
        description="Idle time on the filter-selection screen before a warning countdown starts.",
    )
    filter_select_grace_seconds: int = Field(
        default=10,
        ge=5,
        description="Extra time given after the warning before the current filter/template is kept and the flow continues.",
    )

    final_preview_timeout_seconds: int = Field(
        default=30,
        ge=10,
        description="Idle time on the final preview screen before the print is triggered automatically.",
    )
    printing_mock_seconds: int = Field(
        default=3,
        ge=1,
        le=30,
        description="How long the mock printing animation/meter runs.",
    )
    qr_download_seconds: int = Field(
        default=8,
        ge=3,
        le=90,
        description="How long the download-QR screen is shown before moving on to the thank-you screen.",
    )
    thank_you_seconds: int = Field(
        default=9,
        ge=2,
        le=30,
        description="How long the thank-you screen is shown before the kiosk resets to idle.",
    )
    timelapse_render_mock_seconds: int = Field(
        default=6,
        ge=1,
        le=60,
        description="Reserved timing hint for a future background timelapse render job (not consumed by the current client-side recorder).",
    )

    digital_delivery_default_enabled: bool = Field(
        default=True,
        description="Default state of the 'digital file + timelapse video' toggle on the package-selection screen.",
    )
    digital_delivery_retention_days: int = Field(
        default=7,
        ge=1,
        le=90,
        description="Number of days the digital download (originals + final image + timelapse) is kept on Cloudflare R2. "
        "Older sessions are deleted automatically (checked at startup and hourly).",
    )
    cloud_delivery_enabled: bool = Field(
        default=True,
        description="Upload the digital files to Cloudflare R2 and link the QR code to the public page. "
        "Needs R2_ENDPOINT, R2_BUCKET, R2_PUBLIC_URL, R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY in the environment or the .env file; "
        "without them the kiosk falls back to the local gallery link.",
    )

    reduce_motion: bool = Field(
        default=False,
        description="Replace the block page transitions and decorative animations by short fades. Enable on slow kiosk hardware if animations stutter.",
    )
    browser_camera_fallback: bool = Field(
        default=True,
        description="When the server camera fails, take photos with the browser camera instead (laptop webcam, or the phone/tablet front camera).",
    )
    sound_enabled: bool = Field(
        default=True,
        description="Play short interface sounds (pop, whoosh, shutter, chime) on the kiosk.",
    )

    filters: list[FramebootFilterDefinition] = Field(
        default=[
            FramebootFilterDefinition(id="natural", name="Natural", css_filter="none"),
            FramebootFilterDefinition(id="vivid", name="Vivid", css_filter="saturate(1.35) contrast(1.1)"),
            FramebootFilterDefinition(id="warm", name="Warm", css_filter="sepia(.16) saturate(1.2) brightness(1.04)"),
            FramebootFilterDefinition(id="mono", name="B&W", css_filter="grayscale(1) contrast(1.08)"),
            FramebootFilterDefinition(id="film", name="Film", css_filter="sepia(.24) contrast(1.08) saturate(.92)"),
        ],
        description="Color filters offered to the guest. Each id must have a matching implementation in services/framebooth/filters.py.",
    )

    support_hotline: str = Field(
        default="",
        description="Support phone number shown to the guest on the device-error screen (printer out of paper, …).",
    )
    printer_retry_count: int = Field(
        default=1,
        ge=0,
        le=5,
        description="Number of automatic retries on a print failure.",
    )

    # ───── capture ─────
    pose_seconds_options: list[int] = Field(
        default=[5, 10, 20],
        min_length=1,
        max_length=4,
        description="Posing times (seconds per shot) the guest can pick on the 'get ready' screen. "
        "The one closest to capture_countdown_seconds is preselected.",
    )

    # ───── payment ─────
    bank_bin: str = Field(
        default="",
        pattern=r"^([0-9]{6})?$",
        description="6-digit NAPAS BIN of the bank receiving transfers (e.g. 970436 Vietcombank, 970422 MB, 970407 Techcombank, "
        "970415 VietinBank, 970418 BIDV, 970423 TPBank, 970416 ACB). Empty: the kiosk shows no bank QR, payment by staff PIN only.",
    )
    bank_account_number: str = Field(
        default="",
        pattern=r"^[0-9A-Za-z]{0,19}$",
        description="Account number receiving the transfers (VietQR).",
    )
    bank_account_name: str = Field(
        default="",
        description="Account holder name shown under the QR, upper case without accents (e.g. NGUYEN VAN A).",
    )
    payment_qr_expiry_seconds: int = Field(
        default=300,
        ge=60,
        le=1800,
        description="Lifetime of a payment QR. After it the kiosk offers to create a new one.",
    )
    vouchers: list[FramebootVoucher] = Field(
        default=[],
        description="Discount codes guests can type on the payment screen. Loyalty rewards are issued automatically on top of these.",
    )

    # ───── result & print ─────
    print_enabled: bool = Field(
        default=False,
        description="Send the collage to the printer of the first share/print action. "
        "Off: the kiosk only shows the print animation (testing without printer).",
    )
    extra_copy_price: int = Field(
        default=15_000,
        ge=0,
        description="Price in VND of each extra print copy beyond the first one.",
    )
    max_print_copies: int = Field(
        default=4,
        ge=1,
        le=10,
        description="Maximum number of copies a guest can print in one session. 1 hides the copies picker.",
    )

    social_handle: str = Field(
        default="",
        max_length=40,
        description="Shop page shown on the story images of the download page, e.g. @tslphotobooth (empty: hidden).",
    )
    social_hashtag: str = Field(
        default="#TSLbooth",
        max_length=40,
        description="Hashtag added to the suggested captions of the download page.",
    )

    # ───── after the print ─────
    loyalty_enabled: bool = Field(
        default=True,
        description="Offer guests to collect a stamp per session with their phone number.",
    )
    loyalty_stamps_for_reward: int = Field(
        default=5,
        ge=2,
        le=20,
        description="Number of sessions after which the guest receives a free-session code.",
    )
    loyalty_reward_valid_days: int = Field(
        default=90,
        ge=7,
        le=365,
        description="Days the free-session code stays valid.",
    )

