import { getJson, postBlobForJson, postForBlob, postJson } from "./client";
import * as demo from "./demo";
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

/** Public demo build (Vercel): no backend, everything is served by ./demo.ts. */
export const DEMO = import.meta.env.VITE_DEMO === "1";

/** MJPEG live-view stream (used directly as an <img> src). */
export const LIVE_STREAM_URL = DEMO ? demo.DEMO_LIVE_URL : "/api/aquisition/stream.mjpg";

export function getConfig(): Promise<KioskConfig> {
  if (DEMO) return demo.getConfig();
  return getJson<KioskConfig>(`${BASE}/config`);
}

export function capture(): Promise<CaptureResult> {
  if (DEMO) return demo.capture();
  return postJson<CaptureResult>(`${BASE}/capture`);
}

/** Whether the server camera can take photos right now (false: webcam busy, crashed or not configured). */
export async function serverCameraAvailable(): Promise<boolean> {
  if (DEMO) return false;
  try {
    return (await getJson<{ available: boolean }>(`${BASE}/camera-status`)).available;
  } catch {
    return false;
  }
}

/** Store a photo taken with the browser camera as a capture of the current session. */
export function uploadCapture(blob: Blob): Promise<CaptureResult> {
  if (DEMO) return demo.addBrowserCapture(blob);
  return postBlobForJson<CaptureResult>(`${BASE}/captures/upload`, blob);
}

export function templatePreviewUrl(templateId: string): string {
  return `${BASE}/templates/${encodeURIComponent(templateId)}/preview`;
}

export function compositePreview(templateId: string, captureIds: string[], filterId: string): Promise<Blob> {
  if (DEMO) return demo.compositePreview(templateId, captureIds, filterId);
  return postForBlob(`${BASE}/templates/${encodeURIComponent(templateId)}/composite-preview`, {
    capture_ids: captureIds,
    filter_id: filterId,
  });
}

export function renderTimelapse(payload: TimelapsePayload): Promise<TimelapseResult> {
  if (DEMO) return demo.renderTimelapse(payload);
  return postJson<TimelapseResult>(`${BASE}/timelapse`, payload);
}

export function renderCollage(payload: RenderPayload): Promise<RenderResult> {
  if (DEMO) return demo.renderCollage(payload);
  return postJson<RenderResult>(`${BASE}/render`, payload);
}

export function verifyPin(pin: string): Promise<PinResult> {
  if (DEMO) return demo.verifyPin(pin);
  return postJson<PinResult>(`${BASE}/verify-pin`, { pin });
}
