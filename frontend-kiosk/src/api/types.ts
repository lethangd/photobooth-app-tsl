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
}

export interface RenderPayload {
  template_id: string;
  capture_ids: string[];
  all_capture_ids: string[];
  filter_id: string;
  session_id: string | null;
  digital_delivery: boolean;
  timelapse_id: string | null;
}

export interface TimelapsePayload {
  capture_ids: string[];
  filter_id: string;
  session_id: string | null;
}

export interface PinResult {
  ok: boolean;
  locked_seconds: number;
}
