import { getJson, postForBlob, postJson } from "./client";
import type {
  CaptureResult,
  KioskConfig,
  PinResult,
  RenderPayload,
  RenderResult,
  TimelapsePayload,
  TimelapseResult,
} from "./types";

const BASE = "/api/framebooth";

/** MJPEG live-view stream (used directly as an <img> src). */
export const LIVE_STREAM_URL = "/api/aquisition/stream.mjpg";

export function getConfig(): Promise<KioskConfig> {
  return getJson<KioskConfig>(`${BASE}/config`);
}

export function capture(): Promise<CaptureResult> {
  return postJson<CaptureResult>(`${BASE}/capture`);
}

export function templatePreviewUrl(templateId: string): string {
  return `${BASE}/templates/${encodeURIComponent(templateId)}/preview`;
}

export function compositePreview(templateId: string, captureIds: string[], filterId: string): Promise<Blob> {
  return postForBlob(`${BASE}/templates/${encodeURIComponent(templateId)}/composite-preview`, {
    capture_ids: captureIds,
    filter_id: filterId,
  });
}

export function renderTimelapse(payload: TimelapsePayload): Promise<TimelapseResult> {
  return postJson<TimelapseResult>(`${BASE}/timelapse`, payload);
}

export function renderCollage(payload: RenderPayload): Promise<RenderResult> {
  return postJson<RenderResult>(`${BASE}/render`, payload);
}

export function verifyPin(pin: string): Promise<PinResult> {
  return postJson<PinResult>(`${BASE}/verify-pin`, { pin });
}
