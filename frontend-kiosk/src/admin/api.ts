/** Admin API client: bearer token in localStorage, 401 sends the user back to the login page. */
import { ref } from "vue";

const TOKEN_KEY = "tsl-admin-token";

function readToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

export const token = ref(readToken());

export function setToken(value: string): void {
  token.value = value;
  try {
    if (value) localStorage.setItem(TOKEN_KEY, value);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* private mode: keep the token in memory only */
  }
}

export class AdminApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail))
      return body.detail.map((item: { msg?: string }) => item.msg ?? "").join(", ");
  } catch {
    /* not json */
  }
  return `${response.status} ${response.statusText}`;
}

export async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (token.value) headers.set("Authorization", `Bearer ${token.value}`);
  let response: Response;
  try {
    response = await fetch(path, { ...init, headers });
  } catch (cause) {
    throw new AdminApiError(cause instanceof Error ? cause.message : "Mất kết nối tới máy chủ", 0);
  }
  if (response.status === 401) {
    setToken("");
    throw new AdminApiError("Phiên đăng nhập đã hết hạn", 401);
  }
  if (!response.ok) throw new AdminApiError(await errorMessage(response), response.status);
  return response;
}

export async function getJson<T>(path: string): Promise<T> {
  return (await (await request(path)).json()) as T;
}

export async function sendJson<T>(path: string, method: string, body?: unknown): Promise<T> {
  const response = await request(path, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export async function login(password: string): Promise<void> {
  const form = new URLSearchParams({ username: "admin", password });
  const response = await fetch("/api/admin/auth/token", { method: "POST", body: form });
  if (!response.ok)
    throw new AdminApiError(
      response.status === 401 ? "Sai mật khẩu" : await errorMessage(response),
      response.status,
    );
  const body = (await response.json()) as { access_token: string };
  setToken(body.access_token);
}

/** Download a protected file (CSV, board image) with the bearer token. */
export async function downloadFile(path: string, filename: string, init?: RequestInit): Promise<void> {
  const blob = await (await request(path, init)).blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export const KIOSK = "/api/admin/kiosk";

// ───────── shapes returned by /api/admin/kiosk ─────────

export interface DayStats {
  day: string;
  first_day: string;
  sessions: number;
  revenue: number;
  printed: number;
  retake_revenue: number;
  retake_shots: number;
  digital: number;
  average_ticket: number;
  pin_ok: number;
  pin_failed: number;
  pin_locked: number;
  by_hour: { hour: number; sessions: number; revenue: number }[];
  by_package: { slot_count: number; sessions: number }[];
  previous: { revenue: number; sessions: number };
  series: { day: string; sessions: number; revenue: number }[];
}

export interface SessionRow {
  session_id: string;
  created_at: string;
  slot_count: number;
  package_price: number;
  retake_shots: number;
  retake_amount: number;
  total: number;
  digital: boolean | null;
  printed_at: string | null;
  mediaitem_id: string | null;
  cloud_url: string | null;
}

export interface PinEvent {
  id: number;
  created_at: string;
  session_id: string | null;
  purpose: "package" | "retake";
  amount: number;
  ok: boolean;
  locked: boolean;
}

export interface SessionDetail extends SessionRow {
  pin_events: PinEvent[];
  media_url: string | null;
}

export interface PrinterFlag {
  key: string;
  label: string;
  severity: "info" | "warning" | "error";
}

export interface PrinterInfo {
  name: string;
  driver: string;
  port: string;
  jobs: number;
  flags: PrinterFlag[];
  severity: "ok" | "info" | "warning" | "error";
  summary: string;
}

export interface PrinterStatus {
  configured_name: string;
  default_name: string;
  kiosk_printer: PrinterInfo | null;
  kiosk_printer_found: boolean;
  printers: PrinterInfo[];
}

export interface Overview {
  camera: {
    running: boolean;
    backend: string | null;
    description: string;
    device: string;
    count: number;
    browser_fallback: boolean;
  };
  printer: PrinterStatus;
  cloud: {
    enabled: boolean;
    available: boolean;
    retention_days: number;
    objects: number;
    bytes: number;
    bucket: string | null;
    public_url: string | null;
  };
}

export interface FrameInfo {
  id: string;
  name: string;
  frame_type: string;
  width: number;
  height: number;
  slot_count: number;
  preview_url: string;
  file_name: string;
  file_size: number;
  placeholder: string;
  slots: { x: number; y: number; width: number; height: number }[];
}

export interface MulticamInfo {
  configured: boolean;
  nodes: { index: number; description: string; address: string }[];
  calibrated: boolean;
  frame_duration_ms: number;
}
