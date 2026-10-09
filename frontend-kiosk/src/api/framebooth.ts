import { getJson, postBlobForJson, postForBlob, postJson } from "./client";
import * as demo from "./demo";
import type {
  CaptureResult,
  KioskConfig,
  LoyaltyResult,
  Payment,
  PaymentPurpose,
  PinContext,
  PinResult,
  PrintStatus,
  RenderPayload,
  RenderResult,
  TimelapsePayload,
  TimelapseResult,
  VoucherCheck,
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

export interface CameraStatus {
  /** the server camera delivers frames right now (false: webcam busy, crashed or not configured) */
  available: boolean;
  /** only the demo "VirtualCamera" is configured, no real camera is connected */
  virtual: boolean;
}

export async function serverCameraStatus(): Promise<CameraStatus> {
  if (DEMO) return { available: false, virtual: false };
  try {
    const status = await getJson<Partial<CameraStatus>>(`${BASE}/camera-status`);
    return { available: Boolean(status.available), virtual: Boolean(status.virtual) };
  } catch {
    return { available: false, virtual: false };
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

export function verifyPin(pin: string, context?: PinContext): Promise<PinResult> {
  if (DEMO) return demo.verifyPin(pin, context?.reference);
  return postJson<PinResult>(`${BASE}/verify-pin`, { pin, ...context });
}

// ───── payments ─────

export function createPayment(
  sessionId: string,
  purpose: PaymentPurpose,
  quantity: number,
  voucherCode?: string | null,
): Promise<Payment> {
  if (DEMO) return demo.createPayment(sessionId, purpose, quantity, voucherCode);
  return postJson<Payment>(`${BASE}/payments`, {
    session_id: sessionId,
    purpose,
    quantity,
    voucher_code: voucherCode || null,
  });
}

export function getPayment(reference: string): Promise<Payment> {
  if (DEMO) return demo.getPayment(reference);
  return getJson<Payment>(`${BASE}/payments/${encodeURIComponent(reference)}`);
}

export function renewPayment(reference: string): Promise<Payment> {
  if (DEMO) return demo.getPayment(reference, true);
  return postJson<Payment>(`${BASE}/payments/${encodeURIComponent(reference)}/renew`);
}

export function cancelPayment(reference: string): Promise<unknown> {
  if (DEMO) return Promise.resolve({ ok: true });
  return postJson(`${BASE}/payments/${encodeURIComponent(reference)}/cancel`);
}

export function checkVoucher(code: string, slotCount: number): Promise<VoucherCheck> {
  if (DEMO) return demo.checkVoucher(code, slotCount);
  return postJson<VoucherCheck>(`${BASE}/vouchers/check`, { code, slot_count: slotCount });
}

// ───── after the print ─────

export function addLoyaltyStamp(sessionId: string, phone: string): Promise<LoyaltyResult> {
  if (DEMO) return demo.addLoyaltyStamp(phone);
  return postJson<LoyaltyResult>(`${BASE}/loyalty`, { session_id: sessionId, phone });
}

export function sendFeedback(
  sessionId: string,
  feedback: { rating?: number; share_consent?: boolean },
): Promise<unknown> {
  if (DEMO) return Promise.resolve({ ok: true });
  return postJson(`${BASE}/feedback`, { session_id: sessionId, ...feedback });
}

export function printerStatus(): Promise<PrintStatus> {
  if (DEMO) return Promise.resolve({ ok: true });
  return getJson<PrintStatus>(`${BASE}/printer-status`);
}

export function printAgain(mediaId: string, copies: number, sessionId: string): Promise<PrintStatus> {
  if (DEMO) return Promise.resolve({ ok: true, simulated: true });
  return postJson<PrintStatus>(`${BASE}/print`, { media_id: mediaId, copies, session_id: sessionId });
}
