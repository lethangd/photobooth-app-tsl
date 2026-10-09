// Hand-written mirror of the /api/framebooth/* responses
// (routers/api/framebooth.py). Run `pnpm gen:api` against a running backend to
// regenerate src/api/schema.ts from OpenAPI if you prefer generated types.

export interface FilterOption {
  id: string;
  name: string;
  css_filter: string;
}

export interface FrameTemplateSummary {
  id: string;
  frame_type: string;
  name: string;
  width: number;
  height: number;
  slot_count: number;
  preview_url: string;
}

export interface FrameTypeConfig {
  slot_count: number;
  shots_to_take: number;
  price: number;
  templates: FrameTemplateSummary[];
}

export interface KioskConfig {
  package_select_timeout_seconds: number;
  shot_buffer_count: number;
  countdown_seconds: number;
  get_ready_seconds: number;
  payment_mock_seconds: number;
  payment_timeout_seconds: number;
  photo_select_warn_seconds: number;
  photo_select_grace_seconds: number;
  filter_select_warn_seconds: number;
  filter_select_grace_seconds: number;
  final_preview_timeout_seconds: number;
  printing_mock_seconds: number;
  qr_download_seconds: number;
  thank_you_seconds: number;
  digital_delivery_default_enabled: boolean;
  digital_delivery_retention_days: number;
  timelapse_render_mock_seconds: number;
  retake_price: number;
  retake_max_shots: number;
  reduce_motion: boolean;
  sound_enabled: boolean;
  browser_camera_fallback?: boolean;
  pose_seconds_options?: number[];
  payment_qr_expiry_seconds?: number;
  /** a bank account is configured: show a VietQR code */
  bank_qr?: boolean;
  /** transfers are confirmed automatically (SePay) */
  auto_confirm?: boolean;
  extra_copy_price?: number;
  max_print_copies?: number;
  print_enabled?: boolean;
  loyalty_enabled?: boolean;
  loyalty_stamps_for_reward?: number;
  support_hotline?: string;
  has_vouchers?: boolean;
  filters: FilterOption[];
  frame_types: FrameTypeConfig[];
}

export interface CaptureResult {
  id: string;
  preview_url: string;
}

export interface TimelapseResult {
  id: string;
  video_url: string;
  status: string;
}

export interface RenderResult {
  id: string;
  media_url: string;
  gallery_url: string;
  download_url: string;
  cloud_url: string | null;
  retention_days: number;
  timelapse_status: string;
  print?: PrintStatus;
}

/** Result of sending a print; `ok: false` carries what the device-error screen shows. */
export interface PrintStatus {
  ok: boolean;
  simulated?: boolean;
  code?: string;
  key?: string;
  label?: string;
}

export interface RenderPayload {
  template_id: string;
  capture_ids: string[];
  all_capture_ids: string[];
  filter_id: string;
  session_id: string | null;
  digital_delivery: boolean;
  timelapse_id: string | null;
  copies?: number;
  share_consent?: boolean;
  /** transparent PNG data URL with the guest's stickers / text / drawing */
  overlay_png?: string | null;
}

export interface TimelapsePayload {
  capture_ids: string[];
  filter_id: string;
  session_id: string | null;
}

/** What the staff confirms with the PIN; the server derives the amount from its own prices. */
export interface PinContext {
  session_id: string;
  purpose: PaymentPurpose;
  slot_count?: number;
  retake_shots?: number;
  /** the payment request being confirmed */
  reference?: string;
}

export type PaymentPurpose = "package" | "retake" | "copies";

/** A payment request: what to pay, the VietQR text and how much already arrived by transfer. */
export interface Payment {
  reference: string;
  session_id: string;
  purpose: PaymentPurpose;
  quantity: number;
  list_amount: number;
  discount: number;
  voucher_code: string | null;
  amount: number;
  received: number;
  remaining: number;
  status: "pending" | "partial" | "paid" | "cancelled";
  method: string | null;
  expires_in: number;
  expired: boolean;
  qr_payload: string | null;
  bank_account_name: string;
  auto_confirm: boolean;
}

export interface VoucherCheck {
  ok: boolean;
  message?: string;
  code?: string;
  discount?: number;
  total?: number;
  label?: string;
}

export interface LoyaltyResult {
  stamps: number;
  sessions: number;
  target: number;
  new_stamp: boolean;
  reward_code: string | null;
  reward_valid_until: string | null;
}

export interface PinResult {
  ok: boolean;
  locked_seconds: number;
}
