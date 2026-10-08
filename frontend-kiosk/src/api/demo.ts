/**
 * Offline stand-in for the photobooth backend, used by the public demo build
 * (`pnpm build:demo`, VITE_DEMO=1). Captures cycle through bundled sample photos,
 * collages are drawn on a canvas and the staff PIN is always 1234.
 */
import s1 from "@/assets/samples/s1.webp";
import s2 from "@/assets/samples/s2.webp";
import s3 from "@/assets/samples/s3.webp";
import s4 from "@/assets/samples/s4.webp";
import s5 from "@/assets/samples/s5.webp";
import s6 from "@/assets/samples/s6.webp";
import s7 from "@/assets/samples/s7.webp";
import circle from "@/assets/samples/circle.webp";

import type {
  CaptureResult,
  FilterOption,
  FrameTemplateSummary,
  KioskConfig,
  PinResult,
  RenderPayload,
  RenderResult,
  TimelapsePayload,
  TimelapseResult,
} from "./types";

export const DEMO_PIN = "1234";
export const DEMO_LIVE_URL = circle;

const SAMPLES = [s1, s5, s2, s6, s3, s7, s4];
const FILTERS: FilterOption[] = [
  { id: "natural", name: "Tự nhiên", css_filter: "none" },
  { id: "vivid", name: "Rực rỡ", css_filter: "saturate(1.6) contrast(1.05)" },
  { id: "warm", name: "Ấm", css_filter: "sepia(0.35) saturate(1.25)" },
  { id: "bw", name: "Đen trắng", css_filter: "grayscale(1) contrast(1.2)" },
  { id: "film", name: "Film", css_filter: "contrast(0.9) saturate(0.7) sepia(0.2)" },
];
const FRAME_COLORS: { id: string; name: string; paper: string; ink: string }[] = [
  { id: "white", name: "Trắng", paper: "#FFFFFF", ink: "#14161C" },
  { id: "cobalt", name: "Cobalt", paper: "#2B3BFF", ink: "#FFFFFF" },
  { id: "lilac", name: "Lilac", paper: "#C9B8FF", ink: "#14161C" },
  { id: "black", name: "Đen", paper: "#14161C", ink: "#FFFFFF" },
];

const captures = new Map<string, string>();
let captureCount = 0;

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function layout(slots: number): {
  width: number;
  height: number;
  cells: { x: number; y: number; w: number; h: number }[];
} {
  const pad = 40;
  const gap = 24;
  const footer = 120;
  if (slots === 4) {
    const w = 520;
    const h = 400;
    const cells = [0, 1, 2, 3].map((i) => ({
      x: pad + (i % 2) * (w + gap),
      y: pad + Math.floor(i / 2) * (h + gap),
      w,
      h,
    }));
    return { width: pad * 2 + w * 2 + gap, height: pad + h * 2 + gap + footer, cells };
  }
  const w = 560;
  const h = 420;
  const cells = Array.from({ length: slots }, (_, i) => ({ x: pad, y: pad + i * (h + gap), w, h }));
  return { width: pad * 2 + w, height: pad + slots * h + (slots - 1) * gap + footer, cells };
}

function templateSvg(slots: number, paper: string, ink: string): string {
  const { width, height, cells } = layout(slots);
  const rects = cells
    .map((c) => `<rect x="${c.x}" y="${c.y}" width="${c.w}" height="${c.h}" rx="16" fill="#E9ECF2"/>`)
    .join("");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><rect width="100%" height="100%" rx="24" fill="${paper}"/>${rects}<text x="50%" y="${height - 50}" text-anchor="middle" font-family="monospace" font-weight="700" font-size="36" letter-spacing="10" fill="${ink}">TSL</text></svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

function templatesFor(slots: number): FrameTemplateSummary[] {
  const { width, height } = layout(slots);
  return FRAME_COLORS.map((color) => ({
    id: `${slots}-${color.id}`,
    frame_type: String(slots),
    name: `Khung ${color.name}`,
    width,
    height,
    slot_count: slots,
    preview_url: templateSvg(slots, color.paper, color.ink),
  }));
}

export async function getConfig(): Promise<KioskConfig> {
  await wait(200);
  return {
    package_select_timeout_seconds: 90,
    shot_buffer_count: 1,
    countdown_seconds: 3,
    get_ready_seconds: 3,
    payment_mock_seconds: 2,
    payment_timeout_seconds: 300,
    photo_select_warn_seconds: 90,
    photo_select_grace_seconds: 30,
    filter_select_warn_seconds: 90,
    filter_select_grace_seconds: 30,
    final_preview_timeout_seconds: 30,
    printing_mock_seconds: 3,
    qr_download_seconds: 30,
    thank_you_seconds: 9,
    digital_delivery_default_enabled: true,
    digital_delivery_retention_days: 7,
    timelapse_render_mock_seconds: 3,
    retake_price: 10000,
    retake_max_shots: 5,
    reduce_motion: false,
    sound_enabled: true,
    filters: FILTERS,
    frame_types: [2, 3, 4].map((slots, index) => ({
      slot_count: slots,
      shots_to_take: slots + 1,
      price: [50000, 70000, 90000][index],
      templates: templatesFor(slots),
    })),
  };
}

/** A photo taken with the device camera (laptop webcam / phone) in the demo build. */
export async function addBrowserCapture(blob: Blob): Promise<CaptureResult> {
  const id = `demo-${(captureCount += 1)}`;
  const url = URL.createObjectURL(blob);
  captures.set(id, url);
  return { id, preview_url: url };
}

export async function capture(): Promise<CaptureResult> {
  await wait(250);
  const id = `demo-${(captureCount += 1)}`;
  const url = SAMPLES[(captureCount - 1) % SAMPLES.length];
  captures.set(id, url);
  return { id, preview_url: url };
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

async function drawCollage(templateId: string, captureIds: string[], filterId: string): Promise<Blob> {
  const [slotText, colorId] = templateId.split("-");
  const slots = Number(slotText);
  const color = FRAME_COLORS.find((c) => c.id === colorId) ?? FRAME_COLORS[0];
  const { width, height, cells } = layout(slots);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = color.paper;
  ctx.fillRect(0, 0, width, height);

  const filter = FILTERS.find((f) => f.id === filterId)?.css_filter ?? "none";
  const images = await Promise.all(captureIds.map((id) => loadImage(captures.get(id) ?? SAMPLES[0])));
  cells.forEach((cell, i) => {
    const img = images[i];
    if (!img) return;
    // cover-fit the photo into the cell
    const scale = Math.max(cell.w / img.width, cell.h / img.height);
    const sw = cell.w / scale;
    const sh = cell.h / scale;
    ctx.save();
    ctx.beginPath();
    ctx.roundRect(cell.x, cell.y, cell.w, cell.h, 16);
    ctx.clip();
    ctx.filter = filter;
    ctx.drawImage(img, (img.width - sw) / 2, (img.height - sh) / 2, sw, sh, cell.x, cell.y, cell.w, cell.h);
    ctx.restore();
  });
  ctx.fillStyle = color.ink;
  ctx.font = "700 36px monospace";
  ctx.textAlign = "center";
  ctx.fillText("T S L  ·  2 0 2 6", width / 2, height - 50);

  return await new Promise<Blob>((resolve, reject) =>
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("canvas export failed"))),
      "image/jpeg",
      0.9,
    ),
  );
}

export async function compositePreview(
  templateId: string,
  captureIds: string[],
  filterId: string,
): Promise<Blob> {
  return drawCollage(templateId, captureIds, filterId);
}

export async function renderTimelapse(payload: TimelapsePayload): Promise<TimelapseResult> {
  await wait(1800);
  return {
    id: "demo-timelapse",
    video_url: captures.get(payload.capture_ids[0]) ?? SAMPLES[0],
    status: "ready",
  };
}

export async function renderCollage(payload: RenderPayload): Promise<RenderResult> {
  await drawCollage(payload.template_id, payload.capture_ids, payload.filter_id);
  const url = window.location.origin;
  return {
    id: "demo-collage",
    media_url: url,
    gallery_url: url,
    download_url: url,
    cloud_url: url,
    retention_days: 7,
    timelapse_status: "ready",
  };
}

export async function verifyPin(pin: string): Promise<PinResult> {
  await wait(250);
  return { ok: pin === DEMO_PIN, locked_seconds: 0 };
}
