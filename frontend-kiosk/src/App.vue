<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { toDataURL } from "qrcode";

import {
  DEMO,
  LIVE_STREAM_URL,
  cancelPayment,
  capture,
  compositePreview,
  createPayment,
  getPayment,
  printAgain,
  printerStatus,
  renderCollage,
  renderTimelapse,
  renewPayment,
  sendFeedback,
  serverCameraStatus,
  templatePreviewUrl,
  uploadCapture,
} from "@/api/framebooth";
import type {
  CaptureResult,
  FrameTemplateSummary,
  FrameTypeConfig,
  Payment,
  PaymentPurpose,
  PrintStatus,
  RenderResult,
  VoucherCheck,
} from "@/api/types";
import circleImg from "@/assets/samples/circle.webp";
import heroCutout from "@/assets/samples/hero-cutout.webp";
import heroImg from "@/assets/samples/hero.webp";
import s1 from "@/assets/samples/s1.webp";
import s2 from "@/assets/samples/s2.webp";
import s3 from "@/assets/samples/s3.webp";
import s4 from "@/assets/samples/s4.webp";
import s5 from "@/assets/samples/s5.webp";
import s6 from "@/assets/samples/s6.webp";
import s7 from "@/assets/samples/s7.webp";
import stripA from "@/assets/samples/strip-a.webp";
import stripB from "@/assets/samples/strip-b.webp";
import Icon from "@/components/Icon.vue";
import LoyaltyDialog from "@/components/LoyaltyDialog.vue";
import NoticeDialog from "@/components/NoticeDialog.vue";
import PhotoStrip from "@/components/PhotoStrip.vue";
import PinDialog from "@/components/PinDialog.vue";
import Star from "@/components/Star.vue";
import StickerEditor from "@/components/StickerEditor.vue";
import TopBar from "@/components/TopBar.vue";
import TransitionOverlay from "@/components/TransitionOverlay.vue";
import VoucherDialog from "@/components/VoucherDialog.vue";
import { browserCameraSupported, snapshot, startBrowserCamera, stopBrowserCamera } from "@/lib/browserCamera";
import { countUp, flyImage, sleep } from "@/lib/motion";
import * as sfx from "@/lib/sfx";
import { useSessionStore } from "@/stores/session";

type Screen =
  | "loading"
  | "idle"
  | "package"
  | "payment"
  | "paySuccess"
  | "prepare"
  | "capture"
  | "photoSelect"
  | "retake"
  | "filter"
  | "decorate"
  | "final"
  | "deviceError"
  | "qr"
  | "thankYou";
type Move = "forward" | "back" | "bubble" | "shutter" | "instant";
type Point = { x: number; y: number };

const STEP: Partial<Record<Screen, number>> = {
  package: 0,
  payment: 1,
  paySuccess: 1,
  prepare: 2,
  capture: 2,
  photoSelect: 3,
  retake: 3,
  filter: 4,
  decorate: 4,
  final: 5,
  deviceError: 5,
};
const TIMEOUT_BAR_SCREENS: Screen[] = [
  "package",
  "payment",
  "prepare",
  "photoSelect",
  "retake",
  "filter",
  "decorate",
  "qr",
];
const PREPARE_SECONDS = 45;
const PAYMENT_POLL_MS = 2000;
const PACKAGE_PHOTOS: Record<number, string[]> = { 2: [s2, s3], 3: [s5, s6, s7], 4: [s1, s2, s3, s4] };
const PACKAGE_TINTS = ["#A8F0E0", "#5562FF", "#FFD2B8"];
const MARQUEE_IDLE = "CƯỜI LÊN ✦ NHẬN ẢNH NGAY ✦ IN TRONG 1 PHÚT ✦ ẢNH SỐ QUA QR ✦ ";
const MARQUEE_THANKS = "SEE YOU AGAIN ✦ HẸN GẶP LẠI ✦ BESTIES ONLY ✦ ";

const store = useSessionStore();
const overlay = ref<InstanceType<typeof TransitionOverlay> | null>(null);

const screen = ref<Screen>("loading");
const reduced = ref(false);

// timers of the current screen; cleared on every navigation
const timers: number[] = [];
const intervals: number[] = [];
const timerNonce = ref(0);
const timerSeconds = ref(0);
const now = ref(Date.now());

// package
const pickedSlot = ref<number | null>(null);
// payment / pin
const payment = ref<Payment | null>(null);
const paymentQrUrl = ref("");
const paymentExpiresAt = ref(0);
const paidAmount = ref(0);
const paidPurpose = ref<PaymentPurpose>("package");
const shownAmount = ref(0);
const pinOpen = ref(false);
const pinPurpose = ref<PaymentPurpose>("package");
const voucherOpen = ref(false);
const payNotice = ref<"" | "expired" | "mismatch">("");
const remainingQrUrl = ref("");
let paymentPoll = 0;
// prepare
const poseSeconds = ref(10);
const prepareCount = ref(0);
const prepareAppend = ref(false);
// capture
const captureMode = ref<"ready" | "shooting" | "done">("ready");
const captureTarget = ref(0);
const currentShot = ref(0);
const countdown = ref(0);
const captureCaption = ref("Sẵn sàng chưa?");
const captureRunId = ref(0);
const flashOn = ref(false);
const landed = ref(new Set<string>());
const liveFrame = ref<HTMLElement | null>(null);
const shotSlots = ref<HTMLElement[]>([]);
// photo select
const stripSlots: (Element | null)[] = [];
const flying = ref(new Set<string>());
const nopeId = ref("");
// retake
const retakeCount = ref(1);
const retakeTotal = ref(0);
// design & decorate
const designPreviewUrl = ref("");
const sheenNonce = ref(0);
const editor = ref<InstanceType<typeof StickerEditor> | null>(null);
const overlayPng = ref<string | null>(null);
// select: "are you still there?"
const stillThereOpen = ref(false);
const stillThereLeft = ref(0);
// final / printing
const finalPreviewUrl = ref("");
const timelapseUrl = ref("");
const timelapseId = ref<string | null>(null);
const printing = ref(false);
const autoPrintAt = ref(0);
const resultQrUrl = ref("");
const copies = ref(1);
const copiesPaid = ref(false);
const copiesPayOpen = ref(false);
const lastRender = ref<RenderResult | null>(null);
const printProblem = ref<PrintStatus | null>(null);
const problemAt = ref(new Date());
const reprintWaiting = ref(false);
const staffCalled = ref(false);
// qr & thanks
const shareConsent = ref(false);
const loyaltyOpen = ref(false);
const rating = ref(0);
// misc
const errorTitle = ref("");
const errorText = ref("");
const retryAction = ref<(() => void) | null>(null);
const taps = ref<{ id: number; x: number; y: number }[]>([]);
let tapId = 0;
const urlCache = new Map<string, string>();
const stopCounters: (() => void)[] = [];

const frameTypes = computed(() => store.config?.frame_types ?? []);
const popularSlot = computed(
  () =>
    frameTypes.value.find((type) => type.slot_count === 3)?.slot_count ??
    frameTypes.value[1]?.slot_count ??
    null,
);
const highlightedSlot = computed(() => pickedSlot.value ?? popularSlot.value);
const selectedSet = computed(() => new Set(store.selectedCaptureIds));
const stepIndex = computed(() => STEP[screen.value] ?? -1);
const dialogOpen = computed(
  () =>
    pinOpen.value ||
    voucherOpen.value ||
    Boolean(payNotice.value) ||
    stillThereOpen.value ||
    copiesPayOpen.value ||
    loyaltyOpen.value,
);
const showTimeoutBar = computed(
  () => TIMEOUT_BAR_SCREENS.includes(screen.value) && timerSeconds.value > 0 && !dialogOpen.value,
);
const retakePrice = computed(() => store.config?.retake_price ?? 10000);
const retakeMax = computed(() => store.config?.retake_max_shots ?? 5);
const retentionDays = computed(
  () => store.finalResult?.retention_days ?? store.config?.digital_delivery_retention_days ?? 7,
);
const sessionCode = computed(() => `PB·${store.sessionId.slice(-4)}`);
const autoPrintLeft = computed(() => Math.max(0, Math.ceil((autoPrintAt.value - now.value) / 1000)));
const autoPrintProgress = computed(() => {
  const total = (store.config?.final_preview_timeout_seconds ?? 30) * 1000;
  return Math.min(1, Math.max(0, 1 - (autoPrintAt.value - now.value) / total));
});
const pinDescription = computed(() => {
  const due = money(payment.value?.remaining ?? 0);
  if (pinPurpose.value === "retake")
    return `Xác nhận khách đã thanh toán\nchụp lại ${retakeCount.value} lần · ${due}`;
  if (pinPurpose.value === "copies")
    return `Xác nhận khách đã thanh toán\nin thêm ${copies.value - 1} bản · ${due}`;
  return `Xác nhận khách đã thanh toán\ngói ${store.slotCount} ảnh · ${due}`;
});
const pinContext = computed(() => ({
  session_id: store.sessionId,
  purpose: pinPurpose.value,
  reference: payment.value?.reference,
  ...(pinPurpose.value === "retake" ? { retake_shots: retakeCount.value } : {}),
  ...(pinPurpose.value === "package" ? { slot_count: store.slotCount } : {}),
}));
const autoConfirm = computed(() => Boolean(payment.value?.auto_confirm ?? store.config?.auto_confirm));
const paymentLeft = computed(() => Math.max(0, Math.ceil((paymentExpiresAt.value - now.value) / 1000)));
const paymentProgress = computed(() => {
  const total = store.config?.payment_qr_expiry_seconds ?? 300;
  return Math.min(1, Math.max(0, paymentLeft.value / total));
});
const poseOptions = computed(() => store.config?.pose_seconds_options ?? [5, 10, 20]);
const maxCopies = computed(() => Math.max(1, store.config?.max_print_copies ?? 1));
const extraCopyPrice = computed(() => store.config?.extra_copy_price ?? 15000);
const loyaltyTarget = computed(() => store.config?.loyalty_stamps_for_reward ?? 5);
const decorateText = computed(() => {
  const day = new Date();
  return `Hội bạn thân · ${pad2(day.getDate())}.${pad2(day.getMonth() + 1)}`;
});
const stripPhotos = computed(() =>
  Array.from({ length: store.slotCount }, (_, i) => {
    const item = store.selectedCaptures[i];
    return item && !flying.value.has(item.id) ? stableUrl(item.preview_url) : null;
  }),
);
const shotTiles = computed(() =>
  Array.from({ length: captureTarget.value }, (_, i) => {
    const item = store.captures[i];
    return {
      index: i,
      url: item && landed.value.has(item.id) ? stableUrl(item.preview_url) : "",
      current: i === store.captures.length,
    };
  }),
);
const photoColumns = computed(() => (store.captures.length > 6 ? 4 : 3));
const photoRows = computed(() => Math.max(1, Math.ceil(store.captures.length / photoColumns.value)));
const topPill = computed<{ text?: string; tone?: "ready" | "rec" | "holo" }>(() => {
  if (screen.value === "idle") return { text: "Sẵn sàng", tone: "ready" };
  if (screen.value === "capture" && store.digitalDeliveryEnabled) return { text: "Rec", tone: "rec" };
  if (screen.value === "retake")
    return { text: `Chụp lại · ${money(retakePrice.value)} / lần`, tone: "holo" };
  if (screen.value === "qr") return { text: "Ảnh đã in xong", tone: "holo" };
  if (screen.value === "deviceError") return { text: "Cần hỗ trợ", tone: "holo" };
  return {};
});

// ───────────── helpers ─────────────

function money(value: number): string {
  return `${new Intl.NumberFormat("vi-VN").format(value)}đ`;
}

function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

/** Cache-busted URL that stays stable across re-renders (no image reload on every tick). */
function stableUrl(url: string): string {
  if (url.startsWith("data:") || url.startsWith("blob:")) return url;
  let cached = urlCache.get(url);
  if (!cached) {
    cached = `${url}${url.includes("?") ? "&" : "?"}v=${Date.now()}`;
    urlCache.set(url, cached);
  }
  return cached;
}

function templateImage(template: FrameTemplateSummary): string {
  return stableUrl(template.preview_url || templatePreviewUrl(template.id));
}

function centerOf(el: Element | null | undefined): Point | undefined {
  const rect = el?.getBoundingClientRect();
  return rect ? { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 } : undefined;
}

function clearTimers(): void {
  timers.splice(0).forEach((timer) => window.clearTimeout(timer));
  intervals.splice(0).forEach((timer) => window.clearInterval(timer));
  stopCounters.splice(0).forEach((stop) => stop());
  timerSeconds.value = 0;
}

function setTimer(callback: () => void, seconds: number): void {
  const safe = Math.max(0, seconds);
  timers.push(window.setTimeout(callback, safe * 1000));
  timerSeconds.value = safe;
  timerNonce.value += 1;
}

function tick(ms = 250): void {
  intervals.push(window.setInterval(() => (now.value = Date.now()), ms));
}

async function makeQr(value: string): Promise<string> {
  return await toDataURL(value, { width: 720, margin: 1, color: { dark: "#14161C", light: "#FFFFFF" } });
}

function showError(title: string, text: unknown, retry?: () => void): void {
  sfx.error();
  errorTitle.value = title;
  errorText.value = text instanceof Error ? text.message : String(text);
  retryAction.value = retry ?? null;
}

function hideError(): void {
  errorTitle.value = "";
  errorText.value = "";
  retryAction.value = null;
}

/** Change screen behind one of the block transitions. Returns false when a transition is already running. */
async function navigate(
  next: Screen,
  move: Move = "forward",
  origin?: Point,
  check = true,
): Promise<boolean> {
  const layer = overlay.value;
  if (layer?.isRunning()) return false;
  clearTimers();
  const swap = () => {
    screen.value = next;
  };
  if (!layer || move === "instant") {
    swap();
    return true;
  }
  if (move === "bubble") return layer.bubble(swap, origin, check);
  if (move === "shutter") return layer.shutter(swap);
  return layer.capsule(swap, move === "back" ? -1 : 1);
}

// ───────────── session ─────────────

function clearSessionState(): void {
  captureRunId.value += 1;
  if (designPreviewUrl.value.startsWith("blob:")) URL.revokeObjectURL(designPreviewUrl.value);
  if (finalPreviewUrl.value.startsWith("blob:") && finalPreviewUrl.value !== designPreviewUrl.value)
    URL.revokeObjectURL(finalPreviewUrl.value);
  designPreviewUrl.value = "";
  finalPreviewUrl.value = "";
  timelapseUrl.value = "";
  timelapseId.value = null;
  urlCache.clear();
  landed.value = new Set();
  flying.value = new Set();
  pickedSlot.value = null;
  pinOpen.value = false;
  printing.value = false;
  stopPaymentWatch();
  payment.value = null;
  paymentQrUrl.value = "";
  remainingQrUrl.value = "";
  voucherOpen.value = false;
  payNotice.value = "";
  resultQrUrl.value = "";
  overlayPng.value = null;
  stillThereOpen.value = false;
  copies.value = 1;
  copiesPaid.value = false;
  copiesPayOpen.value = false;
  lastRender.value = null;
  printProblem.value = null;
  reprintWaiting.value = false;
  staffCalled.value = false;
  shareConsent.value = false;
  loyaltyOpen.value = false;
  rating.value = 0;
  store.resetSession();
  store.setFinalResult(null);
  hideError();
}

async function returnToIdle(move: Move = "back"): Promise<void> {
  hideError();
  pinOpen.value = false;
  const ok = await navigate("idle", move);
  if (!ok) return;
  clearSessionState();
}

// ───────────── 01 idle → 02 package ─────────────

async function startFromIdle(event: PointerEvent): Promise<void> {
  if (screen.value !== "idle" || errorTitle.value) return;
  const ok = await navigate("package", "bubble", { x: event.clientX, y: event.clientY }, false);
  if (ok) setTimer(() => void returnToIdle(), store.config?.package_select_timeout_seconds ?? 60);
}

async function pickPackage(frameType: FrameTypeConfig): Promise<void> {
  if (overlay.value?.isRunning() || pickedSlot.value !== null) return;
  pickedSlot.value = frameType.slot_count;
  sfx.pop();
  clearTimers();
  store.selectPackage(frameType.slot_count);
  try {
    await openPayment("package", frameType.slot_count);
  } catch (error) {
    pickedSlot.value = null;
    showError("Chưa tạo được mã thanh toán", error, () => void pickPackage(frameType));
    return;
  }
  await sleep(380);
  const ok = await navigate("payment");
  pickedSlot.value = null;
  if (!ok) return;
  shownAmount.value = 0;
  stopCounters.push(
    countUp(0, payment.value?.amount ?? frameType.price, 600, (value) => (shownAmount.value = value)),
  );
  armPaymentScreenTimer();
  startPaymentWatch();
}

async function backToPackage(): Promise<void> {
  stopPaymentWatch();
  if (payment.value) void cancelPayment(payment.value.reference).catch(() => undefined);
  payment.value = null;
  const ok = await navigate("package", "back");
  if (ok) setTimer(() => void returnToIdle(), store.config?.package_select_timeout_seconds ?? 60);
}

// ───────────── 03 payment / PIN / voucher ─────────────

/** Create the payment request (server prices, voucher) and its VietQR image. */
async function openPayment(
  purpose: PaymentPurpose,
  quantity: number,
  voucherCode?: string | null,
): Promise<void> {
  stopPaymentWatch();
  const created = await createPayment(store.sessionId, purpose, quantity, voucherCode);
  await applyPayment(created);
}

async function applyPayment(next: Payment): Promise<void> {
  payment.value = next;
  paymentExpiresAt.value = Date.now() + next.expires_in * 1000;
  now.value = Date.now();
  paymentQrUrl.value = next.qr_payload ? await makeQr(next.qr_payload) : "";
}

function armPaymentScreenTimer(): void {
  // the QR may expire first; the session is only dropped well after that
  const qrSeconds = store.config?.payment_qr_expiry_seconds ?? 300;
  setTimer(() => void returnToIdle(), Math.max(store.config?.payment_timeout_seconds ?? 180, qrSeconds + 60));
  tick(500);
}

function stopPaymentWatch(): void {
  window.clearInterval(paymentPoll);
  paymentPoll = 0;
}

/** Follow the open payment: bank transfers confirmed by the server, and the QR lifetime. */
function startPaymentWatch(): void {
  stopPaymentWatch();
  let polling = false;
  paymentPoll = window.setInterval(async () => {
    const current = payment.value;
    if (!current || polling) return;
    if (
      current.status !== "paid" &&
      !payNotice.value &&
      Date.now() > paymentExpiresAt.value &&
      current.qr_payload
    ) {
      sfx.error();
      payNotice.value = "expired";
    }
    if (!autoConfirm.value) return;
    polling = true;
    try {
      onPaymentUpdate(await getPayment(current.reference));
    } catch (error) {
      console.warn(error);
    } finally {
      polling = false;
    }
  }, PAYMENT_POLL_MS);
}

function onPaymentUpdate(next: Payment): void {
  const previous = payment.value;
  if (!previous || previous.reference !== next.reference) return;
  payment.value = next;
  if (next.status === "paid") {
    void onPaid(centerOf(document.querySelector(".qr-card")) ?? { x: innerWidth / 2, y: innerHeight / 2 });
  } else if (next.status === "partial" && next.received !== previous.received) {
    sfx.error();
    paymentExpiresAt.value = Date.now() + next.expires_in * 1000;
    void (async () => {
      remainingQrUrl.value = next.qr_payload ? await makeQr(next.qr_payload) : "";
      payNotice.value = "mismatch";
    })();
  }
}

async function renewQr(): Promise<void> {
  const current = payment.value;
  if (!current) return;
  try {
    await applyPayment(await renewPayment(current.reference));
    payNotice.value = "";
    sfx.pop();
  } catch (error) {
    showError("Chưa tạo được mã mới", error, () => void renewQr());
  }
}

async function refreshPayment(): Promise<void> {
  const current = payment.value;
  if (!current) return;
  try {
    onPaymentUpdate(await getPayment(current.reference));
  } catch (error) {
    console.warn(error);
  }
}

function callStaff(): void {
  payNotice.value = "";
  openPin(pinPurpose.value);
}

function openVoucher(): void {
  sfx.pop();
  voucherOpen.value = true;
}

async function applyVoucher(result: VoucherCheck): Promise<void> {
  voucherOpen.value = false;
  const previous = payment.value;
  try {
    await openPayment("package", store.slotCount, result.code);
  } catch (error) {
    showError("Chưa áp dụng được mã", error);
    if (previous) await applyPayment(previous);
    startPaymentWatch();
    return;
  }
  const from = shownAmount.value;
  stopCounters.push(countUp(from, payment.value?.amount ?? 0, 500, (value) => (shownAmount.value = value)));
  if (payment.value?.status === "paid") {
    void onPaid(centerOf(document.querySelector(".qr-card")) ?? { x: innerWidth / 2, y: innerHeight / 2 });
    return;
  }
  startPaymentWatch();
}

function openPin(purpose: PaymentPurpose): void {
  sfx.pop();
  pinPurpose.value = purpose;
  pinOpen.value = true;
}

async function onPinSuccess(origin: Point): Promise<void> {
  pinOpen.value = false;
  await onPaid(origin);
}

/** Money arrived (PIN, transfer or a free voucher): go on with what it paid for. */
async function onPaid(origin: Point): Promise<void> {
  const paid = payment.value;
  stopPaymentWatch();
  pinOpen.value = false;
  voucherOpen.value = false;
  payNotice.value = "";
  if (!paid) return;
  if (paid.purpose === "copies") {
    copiesPayOpen.value = false;
    copiesPaid.value = true;
    sfx.chime();
    void printFinal();
    return;
  }
  sfx.chime();
  paidAmount.value = paid.amount;
  paidPurpose.value = paid.purpose;
  prepareCount.value =
    paid.purpose === "retake" ? retakeCount.value : (store.packageConfig?.shots_to_take ?? 0);
  prepareAppend.value = paid.purpose === "retake";
  const ok = await navigate("paySuccess", "bubble", origin, true);
  if (ok) setTimer(() => void openPrepare(), 3);
}

// ───────────── 03c pay success → 03g prepare ─────────────

async function openPrepare(): Promise<void> {
  const options = poseOptions.value;
  const preferred = store.config?.countdown_seconds ?? 10;
  if (!options.includes(poseSeconds.value))
    poseSeconds.value = options.reduce((best, value) =>
      Math.abs(value - preferred) < Math.abs(best - preferred) ? value : best,
    );
  if (!prepareAppend.value) store.clearCaptures();
  captureTarget.value = store.captures.length + prepareCount.value;
  currentShot.value = store.captures.length + 1;
  captureMode.value = "ready";
  const ok = await navigate("prepare");
  if (!ok) return;
  await armCamera();
}

function choosePose(seconds: number): void {
  if (seconds === poseSeconds.value) return;
  sfx.pop();
  poseSeconds.value = seconds;
}

// ───────────── 04 capture ─────────────

/**
 * Where photos come from: the server camera (DSLR / configured webcam), the browser camera
 * (laptop webcam, or the front camera when the kiosk runs on a phone) when the server camera
 * is unusable, or the bundled sample photos in the demo when no camera can be opened at all.
 */
const cameraSource = ref<"server" | "browser" | "samples">("server");
const browserVideo = ref<HTMLVideoElement | null>(null);
let serverCameraUsable = false;

async function useBrowserCamera(): Promise<boolean> {
  // the admin can turn the webcam fallback off (the public demo always allows it)
  if (!DEMO && store.config?.browser_camera_fallback === false) return false;
  if (!browserCameraSupported()) return false;
  cameraSource.value = "browser";
  await nextTick();
  if (!browserVideo.value) return false;
  try {
    await startBrowserCamera(browserVideo.value);
    return true;
  } catch (error) {
    console.warn("browser camera unavailable", error);
    return false;
  }
}

/**
 * Real server camera (DSLR / configured webcam) first. When none is connected, i.e. only the demo
 * VirtualCamera runs, use the laptop webcam (or the phone camera) instead, and the demo camera only
 * as a last resort so the flow keeps working.
 */
async function chooseCameraSource(): Promise<void> {
  const status = await serverCameraStatus();
  serverCameraUsable = status.available;
  if (status.available && !status.virtual) {
    cameraSource.value = "server";
    return;
  }
  if (await useBrowserCamera()) return;
  cameraSource.value = DEMO ? "samples" : "server";
}

/** One photo from the current source; a failing server camera switches to the browser camera once. */
async function takePhoto(): Promise<CaptureResult> {
  if (cameraSource.value === "server") {
    try {
      return await capture();
    } catch (error) {
      if (!(await useBrowserCamera())) throw error;
      await sleep(500); // let the freshly opened camera adjust exposure
    }
  }
  if (cameraSource.value === "browser" && browserVideo.value) {
    return await uploadCapture(await snapshot(browserVideo.value));
  }
  return await capture();
}

async function armCamera(): Promise<void> {
  await chooseCameraSource();
  if (cameraSource.value === "server" && !DEMO && !serverCameraUsable) {
    showError(
      "Không mở được camera",
      "Camera của máy đang bận hoặc chưa kết nối, và trình duyệt cũng không được phép dùng webcam. " +
        "Hãy đóng ứng dụng khác đang dùng camera (Zoom, Teams, Camera…) rồi thử lại.",
      () => void armCamera(),
    );
    return;
  }
  // nobody pressed "start": begin anyway so a paid session never gets stuck
  setTimer(() => void startFromPrepare(), PREPARE_SECONDS);
}

async function startFromPrepare(): Promise<void> {
  if (screen.value !== "prepare" || errorTitle.value) return;
  captureCaption.value = "Tạo dáng nào!";
  const ok = await navigate("capture", "shutter");
  if (!ok) return;
  if (cameraSource.value === "browser") {
    await nextTick();
    if (browserVideo.value) await startBrowserCamera(browserVideo.value).catch(() => undefined);
  }
  await startShooting();
}

// release the webcam as soon as the guest leaves the camera screens
watch(screen, (next) => {
  if (next !== "capture" && next !== "prepare") stopBrowserCamera();
});

function triggerFlash(): void {
  flashOn.value = false;
  requestAnimationFrame(() => {
    flashOn.value = true;
    window.setTimeout(() => (flashOn.value = false), 140);
  });
}

async function runCountdown(seconds: number, runId: number): Promise<boolean> {
  captureCaption.value = "Tạo dáng nào!";
  for (let remaining = seconds; remaining > 0; remaining -= 1) {
    if (captureRunId.value !== runId) return false;
    countdown.value = remaining;
    if (remaining <= 2) captureCaption.value = "Cười thật tươi!";
    await sleep(1000);
  }
  countdown.value = 0;
  return captureRunId.value === runId;
}

async function startShooting(): Promise<void> {
  if (captureMode.value !== "ready" || screen.value !== "capture") return;
  clearTimers();
  captureMode.value = "shooting";
  const runId = captureRunId.value + 1;
  captureRunId.value = runId;

  try {
    while (store.captures.length < captureTarget.value) {
      currentShot.value = store.captures.length + 1;
      if (!(await runCountdown(poseSeconds.value, runId))) return;
      triggerFlash();
      sfx.shutter();
      captureCaption.value = "Bắt được rồi!";
      const shot = await takePhoto();
      if (captureRunId.value !== runId) return;
      store.addCapture(shot);
      await nextTick();
      const slot = shotSlots.value[store.captures.length - 1];
      if (liveFrame.value && slot) {
        await flyImage(
          stableUrl(shot.preview_url),
          liveFrame.value.getBoundingClientRect(),
          slot.getBoundingClientRect(),
          "1.8rem",
          560,
        );
      }
      landed.value = new Set([...landed.value, shot.id]);
      captureCaption.value = store.captures.length >= captureTarget.value ? "Xong rồi!" : "Đẹp lắm!";
      await sleep(350);
    }
    captureMode.value = "done";
    await sleep(400);
    await openPhotoSelect("shutter");
  } catch (error) {
    captureMode.value = "ready";
    showError("Camera chưa phản hồi", error, () => void startShooting());
  }
}

// ───────────── 05 photo select ─────────────

async function openPhotoSelect(move: Move): Promise<void> {
  const ok = await navigate("photoSelect", move);
  if (ok) armSelectTimer();
}

function armSelectTimer(): void {
  clearTimers();
  stillThereOpen.value = false;
  setTimer(() => showStillThere(), store.config?.photo_select_warn_seconds ?? 45);
}

/** 05c · After a while without touches: count down, then pick the first photos and go on. */
function showStillThere(): void {
  if (screen.value !== "photoSelect") return;
  sfx.pop();
  stillThereLeft.value = store.config?.photo_select_grace_seconds ?? 15;
  stillThereOpen.value = true;
  intervals.push(
    window.setInterval(() => {
      stillThereLeft.value -= 1;
      if (stillThereLeft.value === 0) {
        stillThereOpen.value = false;
        autoSelectAndContinue();
      }
    }, 1000),
  );
}

function stillHere(): void {
  sfx.pop();
  armSelectTimer();
}

function setStripSlot(el: Element | null, index: number): void {
  stripSlots[index] = el;
}

async function toggleShot(item: CaptureResult, event: MouseEvent): Promise<void> {
  const card = event.currentTarget as HTMLElement;
  const img = card.querySelector("img");
  const src = stableUrl(item.preview_url);
  armSelectTimer();

  if (selectedSet.value.has(item.id)) {
    const slot = stripSlots[store.selectedCaptureIds.indexOf(item.id)];
    const from = slot?.getBoundingClientRect();
    store.toggleCaptureSelection(item.id);
    sfx.pop();
    if (from && img) await flyImage(src, from, img.getBoundingClientRect(), "2.6rem", 420);
    return;
  }

  if (store.selectedCaptureIds.length >= store.slotCount) {
    sfx.error();
    nopeId.value = "";
    await nextTick();
    nopeId.value = item.id;
    return;
  }

  store.toggleCaptureSelection(item.id);
  sfx.pop();
  flying.value = new Set([...flying.value, item.id]);
  await nextTick();
  const slot = stripSlots[store.selectedCaptureIds.indexOf(item.id)];
  if (slot && img)
    await flyImage(src, img.getBoundingClientRect(), slot.getBoundingClientRect(), "0.8rem", 520);
  const next = new Set(flying.value);
  next.delete(item.id);
  flying.value = next;
}

function autoSelectAndContinue(): void {
  if (!store.hasExactSelection) store.autoSelectFirstN();
  void openFilter();
}

// ───────────── 05b retake ─────────────

async function openRetake(): Promise<void> {
  retakeCount.value = 1;
  retakeTotal.value = retakePrice.value;
  pinPurpose.value = "retake";
  try {
    await openPayment("retake", 1);
  } catch (error) {
    showError("Chưa tạo được mã thanh toán", error, () => void openRetake());
    return;
  }
  const ok = await navigate("retake");
  if (!ok) return;
  setTimer(() => void leaveRetake(), store.config?.payment_timeout_seconds ?? 180);
  tick(500);
  startPaymentWatch();
}

async function leaveRetake(): Promise<void> {
  stopPaymentWatch();
  if (payment.value) void cancelPayment(payment.value.reference).catch(() => undefined);
  payment.value = null;
  payNotice.value = "";
  await openPhotoSelect("back");
}

async function chooseRetake(count: number): Promise<void> {
  if (count === retakeCount.value) return;
  sfx.pop();
  const from = retakeTotal.value;
  retakeCount.value = count;
  stopCounters.push(countUp(from, count * retakePrice.value, 360, (value) => (retakeTotal.value = value)));
  try {
    await openPayment("retake", count);
    startPaymentWatch();
  } catch (error) {
    showError("Chưa tạo được mã thanh toán", error);
  }
}

// ───────────── 06 colour & frame ─────────────

async function refreshDesignPreview(): Promise<void> {
  const template = store.selectedTemplate;
  if (!template || store.selectedCaptureIds.length === 0) return;
  try {
    const blob = await compositePreview(template.id, store.selectedCaptureIds, store.filterId);
    const url = URL.createObjectURL(blob);
    await new Promise<void>((resolve) => {
      const probe = new Image();
      probe.onload = probe.onerror = () => resolve();
      probe.src = url;
    });
    const old = designPreviewUrl.value;
    designPreviewUrl.value = url;
    if (old.startsWith("blob:") && old !== finalPreviewUrl.value)
      window.setTimeout(() => URL.revokeObjectURL(old), 600);
  } catch (error) {
    console.warn(error);
    designPreviewUrl.value = templateImage(template);
  }
}

async function openFilter(move: Move = "forward"): Promise<void> {
  if (!store.hasExactSelection) return;
  store.ensureTemplateSelected();
  overlayPng.value = null; // decorations belong to one collage; redone after changing colour or frame
  // render the preview while the blocks cover the screen
  const preview = refreshDesignPreview();
  const ok = await navigate("filter", move);
  await preview;
  if (ok) {
    const config = store.config;
    setTimer(
      () => void openFinal(),
      (config?.filter_select_warn_seconds ?? 45) + (config?.filter_select_grace_seconds ?? 10),
    );
  }
}

async function chooseFilter(filterId: string): Promise<void> {
  if (filterId === store.filterId) return;
  sfx.pop();
  store.selectFilter(filterId);
  await refreshDesignPreview();
}

async function chooseTemplate(templateId: string): Promise<void> {
  if (templateId === store.selectedTemplateId) return;
  sfx.pop();
  store.selectTemplate(templateId);
  sheenNonce.value += 1;
  await refreshDesignPreview();
}

// ───────────── 06b decorate ─────────────

async function openDecorate(): Promise<void> {
  if (!designPreviewUrl.value || !store.selectedTemplate) return void openFinal();
  const ok = await navigate("decorate");
  if (!ok) return;
  const config = store.config;
  // long idle: keep what was added and move on
  setTimer(
    () => void finishDecorate(),
    (config?.filter_select_warn_seconds ?? 45) * 2 + (config?.filter_select_grace_seconds ?? 10),
  );
}

async function finishDecorate(): Promise<void> {
  if (screen.value !== "decorate") return;
  overlayPng.value = (await editor.value?.exportOverlay()) ?? null;
  await openFinal();
}

function skipDecorate(): void {
  overlayPng.value = null;
  void openFinal();
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

/** Preview of the collage with the guest's decorations on top (the server does the same for the print). */
async function composeFinalPreview(): Promise<string> {
  if (!overlayPng.value || !designPreviewUrl.value) return designPreviewUrl.value;
  try {
    const [photo, deco] = await Promise.all([loadImage(designPreviewUrl.value), loadImage(overlayPng.value)]);
    const canvas = document.createElement("canvas");
    canvas.width = photo.naturalWidth;
    canvas.height = photo.naturalHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return designPreviewUrl.value;
    ctx.drawImage(photo, 0, 0);
    ctx.drawImage(deco, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
    return blob ? URL.createObjectURL(blob) : designPreviewUrl.value;
  } catch (error) {
    console.warn(error);
    return designPreviewUrl.value;
  }
}

// ───────────── 07 result & print ─────────────

async function startTimelapseRender(): Promise<void> {
  if (!store.digitalDeliveryEnabled || store.captures.length < 2) return;
  try {
    const result = await renderTimelapse({
      capture_ids: store.captures.map((item) => item.id),
      filter_id: store.filterId,
      session_id: store.sessionId,
    });
    timelapseId.value = result.id;
    timelapseUrl.value = stableUrl(result.video_url);
  } catch (error) {
    console.warn(error);
  }
}

async function openFinal(move: Move = "forward"): Promise<void> {
  if (!store.selectedTemplate || !store.hasExactSelection) {
    showError("Thiếu ảnh hoặc khung", "Hãy chọn đủ ảnh rồi thử lại.", () => void openFilter());
    return;
  }
  const composed = composeFinalPreview();
  const ok = await navigate("final", move);
  if (!ok) return;
  const preview = await composed;
  if (finalPreviewUrl.value.startsWith("blob:") && finalPreviewUrl.value !== designPreviewUrl.value)
    URL.revokeObjectURL(finalPreviewUrl.value);
  finalPreviewUrl.value = preview;
  if (!timelapseId.value) void startTimelapseRender();
  armAutoPrint();
}

function armAutoPrint(): void {
  const seconds = store.config?.final_preview_timeout_seconds ?? 30;
  autoPrintAt.value = Date.now() + seconds * 1000;
  now.value = Date.now();
  tick();
  setTimer(() => void printFinal(), seconds);
}

function changeCopies(delta: number): void {
  const next = Math.min(maxCopies.value, Math.max(1, copies.value + delta));
  if (next === copies.value) return;
  sfx.pop();
  copies.value = next;
  copiesPaid.value = false;
}

/** More than one print: the extra copies are paid first (QR or staff PIN). */
async function openCopiesPayment(): Promise<void> {
  clearTimers();
  pinPurpose.value = "copies";
  try {
    await openPayment("copies", copies.value - 1);
  } catch (error) {
    showError("Chưa tạo được mã thanh toán", error, () => void openCopiesPayment());
    return;
  }
  copiesPayOpen.value = true;
  tick(500);
  startPaymentWatch();
}

function cancelCopiesPayment(): void {
  stopPaymentWatch();
  if (payment.value) void cancelPayment(payment.value.reference).catch(() => undefined);
  payment.value = null;
  payNotice.value = "";
  copiesPayOpen.value = false;
  copies.value = 1;
  armAutoPrint();
}

async function printFinal(event?: MouseEvent): Promise<void> {
  const template = store.selectedTemplate;
  if (!template || printing.value) return;
  if (copies.value > 1 && !copiesPaid.value) {
    // the guest asked for more copies: pay first; the auto-print timer just prints the included one
    if (event) return void openCopiesPayment();
    copies.value = 1;
  }
  const origin =
    centerOf(event?.currentTarget as Element | undefined) ?? centerOf(document.querySelector(".print-btn"));
  clearTimers();
  printing.value = true;

  try {
    const [result] = await Promise.all([
      renderCollage({
        template_id: template.id,
        capture_ids: store.selectedCaptureIds,
        all_capture_ids: store.captures.map((item) => item.id),
        filter_id: store.filterId,
        session_id: store.sessionId,
        digital_delivery: store.digitalDeliveryEnabled,
        timelapse_id: timelapseId.value,
        copies: copies.value,
        overlay_png: overlayPng.value,
      }),
      sleep((store.config?.printing_mock_seconds ?? 3) * 1000),
    ]);
    store.setFinalResult(result);
    lastRender.value = result;
    const downloadUrl =
      result.cloud_url ?? `${window.location.origin}${result.download_url || result.gallery_url}`;
    resultQrUrl.value = await makeQr(downloadUrl);
    if (result.print && !result.print.ok) {
      await openDeviceError(result.print);
      return;
    }
    await goToQr(origin);
  } catch (error) {
    showError("Chưa in được ảnh", error, () => void printFinal());
  } finally {
    printing.value = false;
  }
}

// ───────────── E1 device error ─────────────

async function openDeviceError(problem: PrintStatus): Promise<void> {
  sfx.error();
  printProblem.value = problem;
  problemAt.value = new Date();
  reprintWaiting.value = false;
  staffCalled.value = false;
  const ok = await navigate("deviceError", "back");
  // nobody around for a long time: hand out the digital photos and finish
  if (ok) setTimer(() => void goToQr(), 600);
}

function waitForPrinter(): void {
  const render = lastRender.value;
  if (reprintWaiting.value || !render) return;
  sfx.pop();
  reprintWaiting.value = true;
  let busy = false;
  intervals.push(
    window.setInterval(async () => {
      if (busy || screen.value !== "deviceError") return;
      busy = true;
      try {
        const status = await printerStatus();
        if (!status.ok) {
          printProblem.value = status;
          return;
        }
        const printed = await printAgain(render.id, copies.value, store.sessionId);
        if (printed.ok) {
          reprintWaiting.value = false;
          sfx.chime();
          await goToQr();
        } else printProblem.value = printed;
      } catch (error) {
        console.warn(error);
      } finally {
        busy = false;
      }
    }, 3000),
  );
}

function callStaffForPrinter(): void {
  sfx.chime();
  staffCalled.value = true;
}

// ───────────── 08 QR → 09 thanks ─────────────

async function goToQr(origin?: Point): Promise<void> {
  const ok = await navigate("qr", origin ? "bubble" : "forward", origin, Boolean(origin));
  if (ok) armQrTimer();
}

function armQrTimer(): void {
  setTimer(() => void openThanks(), store.config?.qr_download_seconds ?? 18);
}

function toggleShareConsent(): void {
  shareConsent.value = !shareConsent.value;
  sfx.pop();
  void sendFeedback(store.sessionId, { share_consent: shareConsent.value }).catch(() => undefined);
}

function openLoyalty(): void {
  sfx.pop();
  clearTimers();
  loyaltyOpen.value = true;
}

function closeLoyalty(): void {
  loyaltyOpen.value = false;
  if (screen.value === "qr") armQrTimer();
}

async function openThanks(): Promise<void> {
  loyaltyOpen.value = false;
  const ok = await navigate("thankYou");
  if (ok) setTimer(() => void returnToIdle("forward"), store.config?.thank_you_seconds ?? 9);
}

function rate(value: number): void {
  if (rating.value) return;
  sfx.chime();
  rating.value = value;
  void sendFeedback(store.sessionId, { rating: value }).catch(() => undefined);
}

// ───────────── global micro-interactions ─────────────

function onPointerDown(event: PointerEvent): void {
  if (stillThereOpen.value) {
    event.preventDefault();
    stillHere();
    return;
  }
  const target = event.target as HTMLElement;
  if (target.closest("button, a, input, label")) return;
  const id = (tapId += 1);
  taps.value = [...taps.value, { id, x: event.clientX, y: event.clientY }];
  window.setTimeout(() => (taps.value = taps.value.filter((tap) => tap.id !== id)), 650);
}

function retryError(): void {
  const retry = retryAction.value;
  hideError();
  retry?.();
}

onMounted(async () => {
  try {
    const config = await store.loadConfig();
    reduced.value = config.reduce_motion;
    sfx.setSoundEnabled(config.sound_enabled);
    clearSessionState();
    screen.value = "idle";
  } catch (error) {
    screen.value = "idle";
    showError("Không tải được kiosk", error, () => window.location.reload());
  }
});

onBeforeUnmount(() => clearTimers());
</script>

<template>
  <div class="app" :class="{ reduced }" :data-screen="screen" @pointerdown.capture="onPointerDown">
    <TopBar
      v-if="screen !== 'thankYou' && screen !== 'loading'"
      :step="stepIndex"
      :pill="topPill.text"
      :pill-tone="topPill.tone"
      :closable="screen === 'package'"
      @close="returnToIdle()"
    />

    <div class="stage">
      <!-- ───────── loading ───────── -->
      <main v-if="screen === 'loading'" class="screen screen--center">
        <span class="chrome-sphere loader-sphere" />
      </main>

      <!-- ───────── 01 idle ───────── -->
      <main v-else-if="screen === 'idle'" class="screen idle" @pointerdown="startFromIdle">
        <div class="deco">
          <div
            class="capsule-deco e-bg"
            style="
              --i: 0;
              --fx: 30rem;
              right: 12rem;
              top: 52rem;
              width: 52rem;
              height: 21rem;
              background: #c9b8ff;
              --rot: -24deg;
            "
          />
          <div
            class="capsule-deco e-bg"
            style="
              --i: 1;
              --fx: -30rem;
              left: -6rem;
              top: 12rem;
              width: 30rem;
              height: 12rem;
              background: #a8f0e0;
              --rot: 18deg;
            "
          />
        </div>

        <section class="idle-copy">
          <div class="kicker-row e-pop" style="--i: 1">
            <span class="mono muted">Self-service photo studio</span>
            <span class="sticker" style="--rot: -4deg">✦ Mới 2026</span>
          </div>
          <h1 class="display idle-title">
            <span class="ln"><span class="e-line" style="--i: 2">Cười lên.</span></span>
            <span class="ln"><span class="e-line accent" style="--i: 3">nhận ảnh</span></span>
            <span class="ln ln--pill"><span class="e-line holo idle-pill" style="--i: 4">ngay!</span></span>
          </h1>
          <div class="cta-wrap e-cta" style="--i: 6">
            <button class="btn btn-primary btn-xl btn-arrowed" type="button">
              Chạm để bắt đầu
              <span class="btn-arrow"><Icon name="arrow-right" :size="29" :stroke="2.6" /></span>
            </button>
          </div>
          <div class="chip-row e-pop" style="--i: 7">
            <span class="pill mono"
              ><i class="pill-dot" style="background: #2b3bff" />{{ pad2(frameTypes.length) }} kiểu
              khung</span
            >
            <span class="pill mono"><i class="pill-dot" style="background: #c9b8ff" />In trong 1 phút</span>
            <span class="pill mono"><i class="pill-dot" style="background: #3fd3b2" />Ảnh số qua QR</span>
          </div>
        </section>

        <section class="idle-art">
          <span class="idle-glow e-bg" style="--i: 0" />
          <!-- the couple steps out of the arch: same photo, cut out, laid over the frame -->
          <div class="idle-arch-wrap e-card" style="--i: 2; --rot: 0deg">
            <div class="idle-arch">
              <div class="idle-arch-inner">
                <img class="idle-arch-photo" :src="heroImg" alt="Khách chụp ảnh tại TSL" />
                <span class="idle-arch-glow" />
              </div>
            </div>
            <img class="idle-arch-cutout" :src="heroCutout" alt="" />
          </div>
          <div class="idle-strip e-card" style="--i: 3; --rot: -8deg"><img :src="stripA" alt="" /></div>
          <div class="idle-circle chrome-ring e-card" style="--i: 4; --rot: 0deg">
            <img :src="circleImg" alt="" />
          </div>
          <div class="idle-badge e-pop" style="--i: 5">
            <div class="chrome-sphere floaty sphere-badge">
              <span class="mono">In ngay</span>
              <span class="display">1 phút</span>
            </div>
          </div>
          <Star
            class="e-pop spin-slow"
            style="--i: 6; position: absolute; left: 28rem; top: 4rem; width: 5.6rem; --rot: 8deg"
          />
          <Star
            class="e-pop spin-slow"
            color="#C9B8FF"
            style="--i: 7; position: absolute; left: 46rem; top: 11rem; width: 3.4rem"
          />
        </section>

        <div class="marquee marquee--cobalt">
          <div class="marquee-track mono">
            <span v-for="n in 4" :key="n">{{ MARQUEE_IDLE }}</span>
          </div>
        </div>
      </main>

      <!-- ───────── 02 package ───────── -->
      <main v-else-if="screen === 'package'" class="screen package">
        <div class="deco">
          <div
            class="capsule-deco e-bg"
            style="
              --i: 0;
              --fx: 30rem;
              right: -12rem;
              bottom: -4rem;
              width: 56rem;
              height: 22rem;
              background: #c9b8ff;
              --rot: -18deg;
            "
          />
          <div
            class="ring-deco e-bg"
            style="--i: 1; --fx: -20rem; left: -14rem; bottom: -14rem; width: 30rem; height: 30rem"
          />
          <Star
            class="e-pop spin-slow"
            style="--i: 3; position: absolute; right: 56rem; top: 2.6rem; width: 6rem"
          />
        </div>

        <div class="screen-head">
          <div>
            <div class="mono muted e-pop" style="--i: 0">Bước 01 — Chọn khung</div>
            <h1 class="display title-md">
              <span class="ln"
                ><span class="e-line" style="--i: 1">Chọn khung <span class="accent">ảnh</span></span></span
              >
            </h1>
          </div>
          <div class="head-hint e-pop" style="--i: 2">Chạm vào một khung</div>
        </div>

        <div class="package-grid" :style="{ '--cols': frameTypes.length || 3 }">
          <div
            v-for="(frameType, index) in frameTypes"
            :key="frameType.slot_count"
            class="e-rise"
            :style="{ '--i': index + 2 }"
          >
            <button
              class="package-card"
              :class="{
                hot: highlightedSlot === frameType.slot_count,
                picked: pickedSlot === frameType.slot_count,
                dimmed: pickedSlot !== null && pickedSlot !== frameType.slot_count,
              }"
              type="button"
              @click="pickPackage(frameType)"
            >
              <span
                class="package-visual"
                :style="{
                  background: highlightedSlot === frameType.slot_count ? '#5562FF' : PACKAGE_TINTS[index % 3],
                }"
              >
                <PhotoStrip
                  class="sway"
                  :photos="PACKAGE_PHOTOS[frameType.slot_count] ?? []"
                  :slots="frameType.slot_count"
                />
                <span
                  v-if="frameType.slot_count === popularSlot"
                  class="sticker package-sticker"
                  style="--rot: -6deg"
                  >✦ Phổ biến</span
                >
                <span v-if="highlightedSlot === frameType.slot_count" class="package-check"
                  ><Icon name="check" :size="22" :stroke="3"
                /></span>
              </span>
              <span class="package-info">
                <span>
                  <span class="display package-name">{{ frameType.slot_count }} ảnh</span>
                  <span class="mono package-sub">Chụp {{ frameType.shots_to_take }} kiểu</span>
                </span>
                <span class="display package-price">{{ money(frameType.price) }}</span>
              </span>
            </button>
          </div>
        </div>

        <label class="digital-toggle e-pop" style="--i: 6">
          <input
            type="checkbox"
            :checked="store.digitalDeliveryEnabled"
            @change="store.toggleDigitalDelivery"
          />
          Nhận thêm ảnh số + video timelapse qua QR
        </label>
      </main>

      <!-- ───────── 03 payment ───────── -->
      <main v-else-if="screen === 'payment'" class="screen pay">
        <div class="deco">
          <div
            class="capsule-deco e-bg"
            style="
              --i: 0;
              --fx: 30rem;
              right: -6rem;
              top: 30rem;
              width: 76rem;
              height: 30rem;
              background: #c9b8ff;
              --rot: -20deg;
            "
          />
          <div
            class="capsule-deco e-bg"
            style="
              --i: 1;
              --fy: 20rem;
              left: 47rem;
              bottom: -4rem;
              width: 32rem;
              height: 13rem;
              background: #a8f0e0;
              --rot: 12deg;
            "
          />
          <div
            class="chrome-sphere e-pop floaty"
            style="--i: 2; position: absolute; left: 66rem; top: 13rem; width: 11rem; height: 11rem"
          />
        </div>

        <section class="pay-copy">
          <div class="kicker-row e-pop" style="--i: 0">
            <span class="mono muted">Bước 02 — Thanh toán</span>
            <span class="sticker" style="--rot: -3deg"
              >✦ Gói {{ store.slotCount }} ảnh · {{ store.shotsToTake }} kiểu</span
            >
            <span v-if="payment?.voucher_code" class="sticker sticker--cobalt" style="--rot: 3deg"
              >{{ payment.voucher_code }} · −{{ money(payment.discount) }}</span
            >
          </div>
          <h1 class="display pay-amount">
            <span class="ln"
              ><span class="e-line" style="--i: 1"
                >{{ money(shownAmount).slice(0, -1) }}<span class="accent">đ</span></span
              ></span
            >
          </h1>
          <div class="pay-text e-pop" style="--i: 2">
            <template v-if="paymentQrUrl"
              >Quét mã chuyển khoản,<br /><span class="accent">hoặc trả tại quầy.</span></template
            >
            <template v-else
              >Thanh toán tại quầy,<br /><span class="accent">nhân viên xác nhận.</span></template
            >
          </div>
          <div class="waiting e-pop" style="--i: 3">
            <i class="waiting-dot" />
            <div>
              <div class="waiting-title">{{ autoConfirm ? "Đang chờ thanh toán" : "Đang chờ xác nhận" }}</div>
              <div class="mono muted waiting-sub">
                {{ autoConfirm ? "Tự động xác nhận khi nhận được tiền" : "Máy tự mở khi nhân viên duyệt" }}
              </div>
            </div>
          </div>
          <div class="row-actions e-cta" style="--i: 4">
            <button class="btn btn-ghost btn-md" type="button" @click="backToPackage">
              <Icon name="arrow-left" :size="22" />
              Đổi khung
            </button>
            <button class="btn btn-dark btn-md" type="button" @click="openPin('package')">
              <Icon name="lock" :size="22" />
              Nhân viên xác nhận · PIN
            </button>
          </div>
          <button
            v-if="store.config?.has_vouchers && !payment?.voucher_code"
            class="mono voucher-link e-pop"
            style="--i: 5"
            type="button"
            @click="openVoucher"
          >
            ✦ Có mã giảm giá? Nhập tại đây
          </button>
        </section>

        <section class="qr-side">
          <PhotoStrip class="e-card qr-side-strip" style="--i: 3; --rot: 10deg" :photos="[s1, s3, s4]" />
          <div class="qr-card chrome-ring e-card" style="--i: 2; --rot: 0deg">
            <span class="sheen" />
            <div class="qr-card-inner">
              <img v-if="paymentQrUrl" class="qr-img" :src="paymentQrUrl" alt="Mã chuyển khoản VietQR" />
              <div v-else class="qr-counter">
                <Icon name="lock" :size="64" :stroke="1.6" />
                <span class="display">Trả tại quầy</span>
                <span class="mono muted">Đọc mã phiên cho nhân viên</span>
              </div>
              <div class="qr-meta">
                <span class="mono muted">Mã phiên</span>
                <span class="display qr-code">{{ sessionCode }}</span>
              </div>
              <div v-if="paymentQrUrl" class="qr-expiry">
                <span class="qr-expiry-bar"><i :style="{ transform: `scaleX(${paymentProgress})` }" /></span>
                <span class="mono"
                  >Hết hạn sau {{ pad2(Math.floor(paymentLeft / 60)) }}:{{ pad2(paymentLeft % 60) }}</span
                >
              </div>
            </div>
          </div>
          <Star
            class="e-pop spin-slow"
            style="--i: 4; position: absolute; left: -3.6rem; top: -3rem; width: 6.4rem"
          />
        </section>
      </main>

      <!-- ───────── 03c payment received ───────── -->
      <main v-else-if="screen === 'paySuccess'" class="screen paid">
        <div class="deco">
          <div
            class="capsule-deco e-bg"
            style="
              --i: 0;
              --fx: 30rem;
              right: -8rem;
              top: 48rem;
              width: 60rem;
              height: 22rem;
              background: #c9b8ff;
              --rot: -18deg;
            "
          />
          <div
            class="capsule-deco e-bg"
            style="
              --i: 1;
              --fx: -30rem;
              left: -6rem;
              top: 10rem;
              width: 34rem;
              height: 13rem;
              background: #a8f0e0;
              --rot: 16deg;
            "
          />
        </div>
        <div class="paid-badge e-pop" style="--i: 0">
          <span class="chrome-sphere paid-sphere" />
          <span class="paid-check"><Icon name="check" :size="72" :stroke="3" /></span>
          <Star class="spin-slow" style="position: absolute; right: -1rem; top: 0.4rem; width: 5.6rem" />
          <Star
            class="spin-slow"
            color="#C9B8FF"
            style="position: absolute; left: -2rem; bottom: 2rem; width: 4rem"
          />
        </div>
        <h1 class="display paid-title">
          <span class="ln"
            ><span class="e-line" style="--i: 1"
              >Thanh toán <span class="accent">thành công!</span></span
            ></span
          >
        </h1>
        <div class="paid-sub e-pop" style="--i: 2">
          Đã nhận {{ money(paidAmount) }} ·
          <template v-if="paidPurpose === 'retake'">Chụp lại {{ prepareCount }} lần</template>
          <template v-else>Gói {{ store.slotCount }} ảnh · {{ store.shotsToTake }} kiểu chụp</template>
        </div>
        <div class="paid-row e-cta" style="--i: 3">
          <span class="pill pill--holo mono">Tự chuyển sang chuẩn bị chụp sau {{ timerSeconds }} giây</span>
          <button class="btn btn-primary btn-lg btn-arrowed" type="button" @click="openPrepare">
            Bắt đầu ngay
            <span class="btn-arrow"><Icon name="arrow-right" :size="23" :stroke="2.6" /></span>
          </button>
        </div>
      </main>

      <!-- ───────── 03g get ready: posing time ───────── -->
      <main v-else-if="screen === 'prepare'" class="screen prep">
        <div class="prep-live chrome-ring e-card" style="--i: 0; --rot: 0deg">
          <div class="prep-live-inner">
            <video
              v-if="cameraSource === 'browser'"
              ref="browserVideo"
              class="live-img live-img--mirror"
              autoplay
              muted
              playsinline
            />
            <img v-else class="live-img" :src="LIVE_STREAM_URL" alt="Camera xem thử" />
            <span class="prep-guide" />
            <span class="pill mono prep-chip">Đứng trong khung nét đứt</span>
          </div>
        </div>
        <aside class="prep-side">
          <div class="mono muted e-pop" style="--i: 1">Bước 03 — Chuẩn bị</div>
          <h1 class="display prep-title">
            <span class="ln"
              ><span class="e-line" style="--i: 2">Sẵn sàng <span class="accent">chưa?</span></span></span
            >
          </h1>
          <ol class="prep-steps">
            <li
              v-for="(step, index) in [
                ['Đứng vào giữa khung', 'Cả nhóm nhìn thấy mặt mình trên màn hình'],
                ['Nhìn vào ống kính', 'Camera ở ngay phía trên màn hình'],
                ['Đổi dáng mỗi kiểu', `${prepareCount} kiểu liên tiếp, bạn chọn thời gian tạo dáng bên dưới`],
              ]"
              :key="index"
              class="e-pop"
              :style="{ '--i': index + 3 }"
            >
              <span class="display prep-num">{{ index + 1 }}</span>
              <div>
                <div class="prep-step-title">{{ step[0] }}</div>
                <div class="prep-step-sub">{{ step[1] }}</div>
              </div>
            </li>
          </ol>
          <div class="mono muted e-pop" style="--i: 6">Thời gian tạo dáng mỗi kiểu</div>
          <div class="prep-poses e-pop" style="--i: 7">
            <button
              v-for="seconds in poseOptions"
              :key="seconds"
              class="display pose-pick"
              :class="{ active: seconds === poseSeconds }"
              type="button"
              :aria-pressed="seconds === poseSeconds"
              @click="choosePose(seconds)"
            >
              {{ seconds }} giây
            </button>
          </div>
          <div class="e-cta" style="--i: 8">
            <button class="btn btn-primary btn-lg btn-arrowed" type="button" @click="startFromPrepare">
              Bắt đầu chụp
              <span class="btn-arrow"><Icon name="camera" :size="24" /></span>
            </button>
          </div>
        </aside>
      </main>

      <!-- ───────── 04 capture ───────── -->
      <main v-else-if="screen === 'capture'" class="screen cap">
        <div class="deco">
          <div
            class="capsule-deco e-bg"
            style="
              --i: 0;
              --fx: 20rem;
              right: -6rem;
              top: 11rem;
              width: 30rem;
              height: 12rem;
              background: #c9b8ff;
              --rot: 20deg;
            "
          />
        </div>
        <div class="live chrome-ring e-card" style="--i: 0; --rot: 0deg">
          <div ref="liveFrame" class="live-inner">
            <video
              v-if="cameraSource === 'browser'"
              ref="browserVideo"
              class="live-img live-img--mirror"
              autoplay
              muted
              playsinline
            />
            <img v-else class="live-img" :src="LIVE_STREAM_URL" alt="Camera" />
            <span v-if="cameraSource === 'browser'" class="pill mono live-source">Camera thiết bị</span>
            <span class="pill mono live-chip"
              >Kiểu {{ pad2(Math.min(currentShot, captureTarget)) }} / {{ pad2(captureTarget) }}</span
            >
            <div v-if="captureMode === 'shooting'" class="count-disc">
              <span class="count-arc" />
              <span v-if="countdown > 0" :key="countdown" class="display count-num">{{ countdown }}</span>
              <Icon v-else class="count-cam" name="camera" :size="96" :stroke="2" />
            </div>
            <div class="flash" :class="{ on: flashOn }" />
          </div>
        </div>

        <aside class="cap-side">
          <div class="mono muted e-pop" style="--i: 1">Bước 03 — Đang chụp</div>
          <div :key="captureCaption" class="display cap-caption caption-pop">{{ captureCaption }}</div>
          <div class="cap-sub e-pop" style="--i: 2">Nhìn thẳng vào ống kính nhé</div>
          <div class="divider" />
          <div class="mono muted">
            Đã chụp · {{ pad2(store.captures.length) }} / {{ pad2(captureTarget) }}
          </div>
          <div class="shot-grid">
            <div
              v-for="tile in shotTiles"
              :key="tile.index"
              ref="shotSlots"
              class="shot-tile"
              :class="{ current: tile.current && captureMode === 'shooting', filled: !!tile.url }"
            >
              <img v-if="tile.url" :src="tile.url" alt="" />
              <span v-else class="display">{{ pad2(tile.index + 1) }}</span>
            </div>
          </div>
        </aside>
      </main>

      <!-- ───────── 05 photo select ───────── -->
      <main v-else-if="screen === 'photoSelect'" class="screen sel">
        <div class="deco">
          <div
            class="capsule-deco e-bg"
            style="
              --i: 0;
              --fx: 20rem;
              right: -4rem;
              top: 10rem;
              width: 28rem;
              height: 11rem;
              background: #a8f0e0;
              --rot: -14deg;
            "
          />
          <Star
            class="e-pop spin-slow"
            style="--i: 2; position: absolute; right: 38rem; top: 1rem; width: 4.4rem"
          />
        </div>
        <section class="sel-main">
          <div class="screen-head">
            <div>
              <div class="mono muted e-pop" style="--i: 0">Bước 04 — Chọn ảnh</div>
              <h1 class="display title-sm">
                <span class="ln"
                  ><span class="e-line" style="--i: 1"
                    >Chọn {{ store.slotCount }} ảnh <span class="accent">đẹp nhất</span></span
                  ></span
                >
              </h1>
            </div>
            <div class="display sel-count e-pop" style="--i: 2">
              <span :key="store.selectedCaptureIds.length" class="sel-count-now">{{
                store.selectedCaptureIds.length
              }}</span>
              <span class="sel-count-of">/ {{ store.slotCount }}</span>
            </div>
          </div>
          <div class="photo-grid" :style="{ '--cols': photoColumns, '--rows': photoRows }">
            <button
              v-for="(item, index) in store.captures"
              :key="item.id"
              class="photo-card e-card"
              :class="{ selected: selectedSet.has(item.id), nope: nopeId === item.id }"
              :style="{ '--i': index + 1, '--rot': '0deg' }"
              type="button"
              :aria-label="`Ảnh ${index + 1}`"
              @click="toggleShot(item, $event)"
            >
              <img :src="stableUrl(item.preview_url)" :alt="`Ảnh ${index + 1}`" />
              <span v-if="selectedSet.has(item.id)" class="display photo-badge">{{
                pad2(store.selectedCaptureIds.indexOf(item.id) + 1)
              }}</span>
            </button>
          </div>
        </section>
        <aside class="sel-side">
          <div class="sel-frame e-card" style="--i: 2; --rot: 0deg">
            <div class="mono muted">Khung của bạn</div>
            <PhotoStrip
              class="sel-strip"
              :photos="stripPhotos"
              :slots="store.slotCount"
              footer="TSL · 2026"
              :slot-refs="setStripSlot"
            />
          </div>
          <div class="e-cta" style="--i: 4">
            <button
              class="btn btn-primary btn-lg btn-arrowed btn-block"
              type="button"
              :disabled="!store.hasExactSelection"
              @click="openFilter()"
            >
              Tiếp tục
              <span class="btn-arrow"><Icon name="arrow-right" :size="24" :stroke="2.6" /></span>
            </button>
          </div>
          <button
            class="btn btn-ghost btn-md btn-block e-pop"
            style="--i: 5"
            type="button"
            @click="openRetake"
          >
            <Icon name="refresh" :size="20" />
            Chụp lại · {{ Math.round(retakePrice / 1000) }}k/lần
          </button>
        </aside>
      </main>

      <!-- ───────── 05b retake ───────── -->
      <main v-else-if="screen === 'retake'" class="screen pay">
        <div class="deco">
          <div
            class="capsule-deco e-bg"
            style="
              --i: 0;
              --fx: 30rem;
              right: -6rem;
              top: 30rem;
              width: 76rem;
              height: 30rem;
              background: #a8f0e0;
              --rot: -20deg;
            "
          />
          <div
            class="chrome-sphere e-pop floaty"
            style="--i: 1; position: absolute; left: 64rem; top: 12rem; width: 12rem; height: 12rem"
          />
          <div
            class="ring-deco e-bg"
            style="--i: 1; --fx: -20rem; left: -15rem; bottom: -15rem; width: 30rem; height: 30rem"
          />
        </div>
        <section class="pay-copy">
          <div class="kicker-row e-pop" style="--i: 0">
            <span class="mono muted">Bước 04B — Chụp lại</span>
            <span class="sticker" style="--rot: -4deg">✦ {{ money(retakePrice) }} / lần</span>
          </div>
          <div>
            <h1 class="display retake-title">
              <span class="ln"><span class="e-line" style="--i: 1">Chụp lại</span></span>
            </h1>
            <div class="retake-sub e-pop" style="--i: 2">Thêm vài kiểu nữa nhé?</div>
          </div>
          <div class="mono muted e-pop" style="--i: 3">Chọn số lần muốn chụp lại</div>
          <div class="retake-picks">
            <button
              v-for="n in retakeMax"
              :key="n"
              class="display retake-pick e-pop"
              :class="{ active: n === retakeCount }"
              :style="{ '--i': n + 3 }"
              type="button"
              :aria-label="`Chụp lại ${n} lần`"
              @click="chooseRetake(n)"
            >
              {{ n }}
            </button>
          </div>
          <div class="retake-total e-pop" style="--i: 6">
            <span class="mono">{{ retakeCount }} lần × {{ money(retakePrice) }} =</span>
            <span class="display accent retake-sum">{{ money(retakeTotal) }}</span>
          </div>
          <div class="waiting e-pop" style="--i: 7">
            <i class="waiting-dot" />
            <div>
              <div class="waiting-title">{{ autoConfirm ? "Đang chờ thanh toán" : "Đang chờ xác nhận" }}</div>
              <div class="mono muted waiting-sub">
                {{
                  autoConfirm ? "Máy tự mở camera khi nhận được tiền" : "Máy tự mở camera khi nhân viên duyệt"
                }}
              </div>
            </div>
          </div>
          <div class="row-actions e-cta" style="--i: 8">
            <button class="btn btn-ghost btn-md" type="button" @click="leaveRetake">
              <Icon name="arrow-left" :size="20" />
              Huỷ
            </button>
            <button class="btn btn-dark btn-md" type="button" @click="openPin('retake')">
              <Icon name="lock" :size="22" />
              Nhân viên xác nhận · PIN
            </button>
          </div>
        </section>
        <section class="qr-side">
          <div class="retake-photo chrome-ring e-card" style="--i: 3; --rot: -10deg">
            <img v-if="store.captures[0]" :src="stableUrl(store.captures[0].preview_url)" alt="" />
          </div>
          <div class="qr-card chrome-ring e-card" style="--i: 2; --rot: 0deg">
            <span class="sheen" />
            <div class="qr-card-inner">
              <img v-if="paymentQrUrl" class="qr-img" :src="paymentQrUrl" alt="Mã chuyển khoản chụp lại" />
              <div v-else class="qr-counter">
                <Icon name="lock" :size="64" :stroke="1.6" />
                <span class="display">Trả tại quầy</span>
                <span class="mono muted">Đọc mã phiên cho nhân viên</span>
              </div>
              <div class="qr-meta">
                <span class="mono muted">Mã phiên</span>
                <span class="display qr-code">{{ sessionCode }}-R</span>
              </div>
            </div>
          </div>
          <Star
            class="e-pop spin-slow"
            style="--i: 4; position: absolute; right: -2.6rem; bottom: -2.6rem; width: 6rem"
          />
        </section>
      </main>

      <!-- ───────── 06 colour & frame ───────── -->
      <main v-else-if="screen === 'filter'" class="screen des">
        <section class="des-preview e-bg" style="--i: 0; --fx: -30rem">
          <span class="mono des-label">Xem trước</span>
          <div class="des-paper e-card" style="--i: 2; --rot: -3deg">
            <Transition name="xfade">
              <img
                v-if="designPreviewUrl"
                :key="designPreviewUrl"
                :src="designPreviewUrl"
                alt="Xem trước ảnh ghép"
              />
            </Transition>
            <span v-if="!designPreviewUrl" class="skeleton" />
            <span v-if="sheenNonce > 0" :key="sheenNonce" class="sheen sheen--once" />
          </div>
          <Star
            class="e-pop spin-slow"
            style="--i: 4; position: absolute; left: 6rem; bottom: 12rem; width: 4.4rem"
          />
        </section>
        <section class="des-controls">
          <div>
            <div class="mono muted e-pop" style="--i: 1">Bước 05 — Màu &amp; viền</div>
            <h1 class="display title-md">
              <span class="ln"
                ><span class="e-line" style="--i: 2"
                  >Chọn màu <span class="accent">&amp;</span> viền</span
                ></span
              >
            </h1>
          </div>
          <div class="des-group">
            <div class="mono muted e-pop" style="--i: 3">Màu ảnh</div>
            <div class="filter-row">
              <button
                v-for="(filter, index) in store.config?.filters"
                :key="filter.id"
                class="filter-card e-pop"
                :class="{ active: filter.id === store.filterId }"
                :style="{ '--i': index + 3 }"
                type="button"
                @click="chooseFilter(filter.id)"
              >
                <img
                  v-if="store.selectedCaptures[0]"
                  :src="stableUrl(store.selectedCaptures[0].preview_url)"
                  :style="{ filter: filter.css_filter }"
                  alt=""
                />
                <span>{{ filter.name }}</span>
              </button>
            </div>
          </div>
          <div class="des-group">
            <div class="mono muted e-pop" style="--i: 5">Viền</div>
            <div class="frame-row">
              <button
                v-for="(template, index) in store.templatesForPackage"
                :key="template.id"
                class="frame-pick e-pop"
                :class="{ active: template.id === store.selectedTemplateId }"
                :style="{ '--i': index + 5 }"
                type="button"
                :aria-label="template.name"
                @click="chooseTemplate(template.id)"
              >
                <img :src="templateImage(template)" alt="" />
                <span v-if="template.id === store.selectedTemplateId" class="frame-check"
                  ><Icon name="check" :size="18" :stroke="3"
                /></span>
              </button>
            </div>
          </div>
          <div class="row-actions e-cta" style="--i: 8">
            <button class="btn btn-ghost btn-md" type="button" @click="openPhotoSelect('back')">
              <Icon name="arrow-left" :size="22" />
              Đổi ảnh
            </button>
            <button class="btn btn-primary btn-md btn-arrowed" type="button" @click="openDecorate">
              Trang trí ảnh
              <span class="btn-arrow"><Icon name="arrow-right" :size="23" :stroke="2.6" /></span>
            </button>
          </div>
          <button class="mono skip-link e-pop" style="--i: 9" type="button" @click="openFinal()">
            Bỏ qua trang trí · xem kết quả
          </button>
        </section>
      </main>

      <!-- ───────── 06b decorate ───────── -->
      <main v-else-if="screen === 'decorate'" class="screen screen--flush">
        <StickerEditor
          ref="editor"
          :preview-url="designPreviewUrl"
          :width="store.selectedTemplate?.width || 1200"
          :height="store.selectedTemplate?.height || 1800"
          :default-text="decorateText"
          @skip="skipDecorate"
          @done="finishDecorate"
        />
      </main>

      <!-- ───────── 07 result & print ───────── -->
      <main v-else-if="screen === 'final'" class="screen res">
        <div class="deco">
          <div
            class="circle-deco e-bg"
            style="
              --i: 0;
              --fx: -30rem;
              left: 5rem;
              top: 7.6rem;
              width: 56rem;
              height: 56rem;
              background: #c9b8ff;
            "
          />
          <div
            class="capsule-deco e-bg"
            style="
              --i: 1;
              --fx: 30rem;
              right: -4rem;
              bottom: 6rem;
              width: 32rem;
              height: 12rem;
              background: #a8f0e0;
              --rot: -16deg;
            "
          />
          <div
            class="chrome-sphere e-pop floaty"
            style="--i: 2; position: absolute; left: 47rem; top: 4rem; width: 10rem; height: 10rem"
          />
        </div>
        <section class="res-print">
          <div class="res-paper print-out">
            <img v-if="finalPreviewUrl" :src="finalPreviewUrl" alt="Ảnh hoàn thiện" />
            <Star class="strip-star" />
          </div>
          <span class="sticker res-sticker e-pop" style="--i: 9; --rot: -12deg">✦ Fresh print</span>
          <Star
            v-for="n in 5"
            :key="n"
            class="burst-star"
            :class="`burst-star--${n}`"
            :color="n % 2 ? '#2B3BFF' : '#C9B8FF'"
          />
        </section>
        <section class="res-copy">
          <div class="mono muted e-pop" style="--i: 1">Bước 06 — Hoàn tất</div>
          <h1 class="display res-title">
            <span class="ln"><span class="e-line" style="--i: 2">Xinh</span></span>
            <span class="ln"><span class="e-line accent" style="--i: 3">quá trời!</span></span>
          </h1>
          <div v-if="store.digitalDeliveryEnabled" class="video-pill e-pop" style="--i: 4">
            <div class="video-thumb">
              <img v-if="timelapseUrl && DEMO" :src="timelapseUrl" alt="" />
              <video v-else-if="timelapseUrl" :src="timelapseUrl" autoplay loop muted playsinline />
              <span v-else class="spinner" />
            </div>
            <div>
              <div class="video-title">Timelapse + GIF boomerang</div>
              <div class="mono video-sub" :class="{ ready: timelapseUrl }">
                {{ timelapseUrl ? "Đã sẵn sàng · gửi qua QR" : "Đang dựng video…" }}
              </div>
            </div>
          </div>
          <div v-if="maxCopies > 1" class="copies e-pop" style="--i: 5">
            <span class="mono muted">Số bản in</span>
            <div class="stepper">
              <button
                class="display step-btn"
                type="button"
                aria-label="Bớt một bản"
                :disabled="copies <= 1 || printing"
                @click="changeCopies(-1)"
              >
                −
              </button>
              <span :key="copies" class="display step-value">{{ copies }}</span>
              <button
                class="display step-btn step-btn--plus"
                type="button"
                aria-label="Thêm một bản"
                :disabled="copies >= maxCopies || printing"
                @click="changeCopies(1)"
              >
                +
              </button>
            </div>
            <span class="copies-note">
              <template v-if="copies > 1"
                >Bản thêm <span class="accent">+{{ money(extraCopyPrice * (copies - 1)) }}</span> · cần thanh
                toán thêm</template
              >
              <template v-else>Gói đã gồm 1 bản in</template>
            </span>
          </div>
          <div class="row-actions e-cta" style="--i: 6">
            <button
              class="btn btn-primary btn-print print-btn"
              type="button"
              :disabled="printing"
              @click="printFinal($event)"
            >
              <span v-if="printing" class="spinner spinner--light" />
              <Icon v-else name="printer" :size="30" />
              {{ printing ? "Đang in…" : copies > 1 ? `In ${copies} bản` : "In ảnh" }}
            </button>
            <button
              class="btn btn-ghost btn-md"
              type="button"
              :disabled="printing"
              @click="openFilter('back')"
            >
              Đổi màu
            </button>
          </div>
          <div v-if="!printing" class="auto-print e-pop" style="--i: 6">
            <span class="mono muted">Tự động in sau {{ autoPrintLeft }} giây</span>
            <span class="auto-bar"><i :style="{ transform: `scaleX(${autoPrintProgress})` }" /></span>
          </div>
        </section>
      </main>

      <!-- ───────── E1 device error (printer) ───────── -->
      <main v-else-if="screen === 'deviceError'" class="screen err">
        <section class="err-copy">
          <div class="error-badge e-pop" style="--i: 0"><Icon name="printer" :size="42" :stroke="2.4" /></div>
          <div class="mono muted e-pop" style="--i: 1">Thông báo sự cố</div>
          <h1 class="display err-title">
            <span class="ln"><span class="e-line" style="--i: 2">Máy in đang</span></span>
            <span class="ln"
              ><span class="e-line err-accent" style="--i: 3">{{
                printProblem?.label || "gặp sự cố"
              }}</span></span
            >
          </h1>
          <div class="err-text e-pop" style="--i: 4">
            Đừng lo, ảnh của bạn đã được lưu an toàn.<br />Nhân viên sẽ đến hỗ trợ trong giây lát.
          </div>
          <div class="chip-row e-pop" style="--i: 5">
            <span class="pill mono">Mã phiên {{ sessionCode }}</span>
            <span v-if="printProblem?.code" class="pill mono">Lỗi {{ printProblem.code }}</span>
            <span class="pill mono"
              >{{ pad2(problemAt.getHours()) }}:{{ pad2(problemAt.getMinutes()) }} ·
              {{ pad2(problemAt.getDate()) }}.{{ pad2(problemAt.getMonth() + 1) }}.{{
                problemAt.getFullYear()
              }}</span
            >
          </div>
        </section>
        <section class="err-options">
          <div class="mono muted e-pop" style="--i: 2">Bạn muốn làm gì?</div>
          <button
            v-if="store.digitalDeliveryEnabled"
            class="err-option err-option--primary e-rise"
            style="--i: 3"
            type="button"
            @click="goToQr()"
          >
            <span class="err-option-icon"><Icon name="download" :size="26" /></span>
            <span>
              <span class="err-option-title">Nhận ảnh số trước</span>
              <span class="err-option-sub">Quét QR tải ảnh, quay lại lấy bản in sau</span>
            </span>
          </button>
          <button
            class="err-option e-rise"
            :class="{ busy: reprintWaiting }"
            style="--i: 4"
            type="button"
            :disabled="reprintWaiting"
            @click="waitForPrinter"
          >
            <span class="err-option-icon">
              <span v-if="reprintWaiting" class="spinner" />
              <Icon v-else name="refresh" :size="26" />
            </span>
            <span>
              <span class="err-option-title">{{ reprintWaiting ? "Đang chờ máy in…" : "Chờ in lại" }}</span>
              <span class="err-option-sub">Máy tự in ngay khi được nạp giấy</span>
            </span>
          </button>
          <button class="err-option e-rise" style="--i: 5" type="button" @click="callStaffForPrinter">
            <span class="err-option-icon"><Icon name="headset" :size="26" /></span>
            <span>
              <span class="err-option-title">{{
                staffCalled ? "Báo nhân viên tại quầy nhé" : "Gọi nhân viên"
              }}</span>
              <span class="err-option-sub">{{
                store.config?.support_hotline
                  ? `Hotline ${store.config.support_hotline}`
                  : "Nhân viên đang ở quầy gần đây"
              }}</span>
            </span>
          </button>
        </section>
      </main>

      <!-- ───────── 08 QR ───────── -->
      <main v-else-if="screen === 'qr'" class="screen pay">
        <div class="deco">
          <div
            class="capsule-deco e-bg"
            style="
              --i: 0;
              --fx: 30rem;
              right: -6rem;
              top: 30rem;
              width: 76rem;
              height: 30rem;
              background: #ffd2b8;
              --rot: -20deg;
            "
          />
          <div
            class="chrome-sphere e-pop floaty"
            style="--i: 1; position: absolute; left: 62rem; top: 12rem; width: 11rem; height: 11rem"
          />
          <div
            class="ring-deco e-bg"
            style="--i: 1; --fx: -20rem; left: -12rem; bottom: -12rem; width: 26rem; height: 26rem"
          />
        </div>
        <section class="pay-copy">
          <div class="mono muted e-pop" style="--i: 0">Bước 07 — Nhận ảnh số</div>
          <h1 v-if="store.digitalDeliveryEnabled" class="display retake-title">
            <span class="ln"><span class="e-line" style="--i: 1">Quét để</span></span>
            <span class="ln"><span class="e-line accent" style="--i: 2">mang về.</span></span>
          </h1>
          <h1 v-else class="display retake-title">
            <span class="ln"><span class="e-line" style="--i: 1">Nhớ lấy</span></span>
            <span class="ln"><span class="e-line accent" style="--i: 2">ảnh nhé!</span></span>
          </h1>
          <div v-if="store.digitalDeliveryEnabled" class="qr-list">
            <div
              v-for="(item, index) in ['Ảnh gốc HD', 'Ảnh ghép', 'Video timelapse', 'GIF boomerang']"
              :key="item"
              class="qr-list-row e-pop"
              :style="{ '--i': index + 3 }"
            >
              <span
                class="mono qr-list-num"
                :style="{ background: ['#C9B8FF', '#A8F0E0', '#FFD2B8', '#C9B8FF'][index] }"
                >{{ pad2(index + 1) }}</span
              >
              <span>{{ item }}</span>
            </div>
          </div>
          <div v-if="store.digitalDeliveryEnabled" class="mono muted e-pop" style="--i: 7">
            Ảnh tự xoá sau {{ retentionDays }} ngày · Có thể xoá ngay trên trang tải ảnh
          </div>
          <label class="consent e-pop" style="--i: 8">
            <input type="checkbox" :checked="shareConsent" @change="toggleShareConsent" />
            Cho phép TSL đăng ảnh lên trang của tiệm (không bắt buộc)
          </label>
          <div class="row-actions e-cta" style="--i: 9">
            <button class="btn btn-primary btn-lg btn-arrowed" type="button" @click="openThanks">
              Xong
              <span class="btn-arrow"><Icon name="arrow-right" :size="25" :stroke="2.6" /></span>
            </button>
            <button
              v-if="store.config?.loyalty_enabled"
              class="btn btn-ghost btn-lg"
              type="button"
              @click="openLoyalty"
            >
              ✦ Tích điểm khách quen
            </button>
          </div>
        </section>
        <section class="qr-side">
          <div class="qr-polaroid chrome-ring drop-in">
            <img
              v-if="store.selectedCaptures[0]"
              :src="stableUrl(store.selectedCaptures[0].preview_url)"
              alt=""
            />
          </div>
          <div
            v-if="store.digitalDeliveryEnabled"
            class="qr-card chrome-ring e-card"
            style="--i: 2; --rot: 0deg"
          >
            <span class="sheen" />
            <div class="qr-card-inner">
              <div class="qr-scan-wrap">
                <img v-if="resultQrUrl" class="qr-img" :src="resultQrUrl" alt="QR nhận ảnh" />
                <span class="scan-line" />
              </div>
              <div class="mono qr-hint">Mở camera điện thoại để quét</div>
            </div>
          </div>
          <div v-else class="res-paper e-card" style="--i: 2; --rot: 3deg">
            <img v-if="finalPreviewUrl" :src="finalPreviewUrl" alt="Ảnh đã in" />
          </div>
          <Star
            class="e-pop spin-slow"
            style="--i: 4; position: absolute; right: -2.8rem; top: -2.8rem; width: 6rem"
          />
        </section>
      </main>

      <!-- ───────── 09 thanks ───────── -->
      <main v-else-if="screen === 'thankYou'" class="screen thanks">
        <div class="deco">
          <div
            class="capsule-deco e-bg"
            style="
              --i: 1;
              --fx: 40rem;
              left: 35rem;
              top: 30rem;
              width: 90rem;
              height: 30rem;
              background: #4655ff;
              --rot: -8deg;
            "
          />
          <div
            class="chrome-sphere confetti-in"
            style="--i: 0; --fx: -40rem; --fy: -30rem; left: 33rem; top: -7rem; width: 22rem; height: 22rem"
          />
          <div
            class="chrome-sphere confetti-in"
            style="--i: 2; --fx: 40rem; --fy: 30rem; right: 33rem; bottom: 12rem; width: 13rem; height: 13rem"
          />
          <span
            class="confetti-in"
            style="
              --i: 3;
              --fx: -30rem;
              --fy: 40rem;
              position: absolute;
              left: 33rem;
              top: 56rem;
              width: 7rem;
            "
          >
            <Star class="spin-slow" color="#A8F0E0" />
          </span>
          <span
            class="confetti-in"
            style="
              --i: 4;
              --fx: 30rem;
              --fy: -40rem;
              position: absolute;
              right: 30rem;
              top: 12rem;
              width: 5rem;
            "
          >
            <Star class="spin-slow" color="#FFD2B8" />
          </span>
          <img
            class="thanks-strip confetti-in"
            :src="stripA"
            alt=""
            style="--i: 1; --fx: -50rem; --fy: -60rem; --rot: -8deg; left: 8rem; top: 6rem"
          />
          <img
            class="thanks-strip confetti-in"
            :src="stripB"
            alt=""
            style="--i: 3; --fx: 50rem; --fy: -60rem; --rot: 7deg; right: 8rem; top: 9rem"
          />
        </div>
        <section class="thanks-copy">
          <span class="sticker e-pop" style="--i: 2; --rot: -3deg">✦ Cảm ơn</span>
          <h1 class="display thanks-title">
            <span class="ln"><span class="e-line" style="--i: 3">Cảm ơn bạn!</span></span>
          </h1>
          <div class="thanks-sub e-pop" style="--i: 4">Hẹn gặp lại ở tấm ảnh tiếp theo.</div>
          <div class="rating e-pop" style="--i: 5">
            <div class="mono rating-label">
              {{ rating ? "Cảm ơn bạn đã góp ý!" : "Bạn thấy trải nghiệm thế nào?" }}
            </div>
            <div class="rating-row">
              <button
                v-for="(label, index) in ['Chưa ổn', 'Ổn', 'Tuyệt vời']"
                :key="label"
                class="rate-btn"
                :class="{ picked: rating === index + 1, faded: rating && rating !== index + 1 }"
                type="button"
                :disabled="Boolean(rating)"
                @click="rate(index + 1)"
              >
                <span class="rate-face">
                  <svg
                    width="26"
                    height="26"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2.2"
                    stroke-linecap="round"
                    aria-hidden="true"
                  >
                    <circle cx="12" cy="12" r="9" />
                    <path d="M9 10h.01M15 10h.01" />
                    <path v-if="index === 0" d="M8.5 16.5a5 5 0 0 1 7 0" />
                    <path v-else-if="index === 1" d="M9 15.5h6" />
                    <path v-else d="M8 14a5 5 0 0 0 8 0" />
                  </svg>
                </span>
                {{ label }}
              </button>
            </div>
          </div>
          <div class="thanks-bar e-pop" style="--i: 6">
            <i :key="timerNonce" :style="{ animationDuration: `${timerSeconds}s` }" />
          </div>
        </section>
        <div class="marquee marquee--white">
          <div class="marquee-track mono">
            <span v-for="n in 4" :key="n">{{ MARQUEE_THANKS }}</span>
          </div>
        </div>
      </main>
    </div>

    <div v-if="showTimeoutBar" :key="timerNonce" class="timeout-bar">
      <i :style="{ animationDuration: `${timerSeconds}s` }" />
    </div>

    <VoucherDialog
      :open="voucherOpen"
      :slot-count="store.slotCount"
      @close="voucherOpen = false"
      @apply="applyVoucher"
    />

    <!-- 03d · QR expired -->
    <NoticeDialog
      :open="payNotice === 'expired'"
      icon="clock"
      title="Mã QR đã hết hạn"
      :text="`Mỗi mã chỉ dùng được trong ${Math.round((store.config?.payment_qr_expiry_seconds ?? 300) / 60)} phút.\nNếu bạn đã chuyển khoản, vui lòng gọi nhân viên.`"
    >
      <template #actions>
        <button class="btn btn-ghost btn-md" type="button" @click="callStaff">Gọi nhân viên</button>
        <button class="btn btn-primary btn-md btn-arrowed" type="button" @click="renewQr">
          Tạo mã mới
          <span class="btn-arrow"><Icon name="refresh" :size="20" :stroke="2.6" /></span>
        </button>
      </template>
    </NoticeDialog>

    <!-- 03e · transfer short of the amount -->
    <NoticeDialog
      :open="payNotice === 'mismatch'"
      icon="alert"
      tone="amber"
      title="Số tiền chưa đủ"
      :width="90"
    >
      <div class="pay-lines">
        <div>
          <span>Cần thanh toán</span><span class="display">{{ money(payment?.amount ?? 0) }}</span>
        </div>
        <div>
          <span>Đã nhận</span><span class="display">{{ money(payment?.received ?? 0) }}</span>
        </div>
        <div>
          <span>Còn thiếu</span
          ><span class="display accent pay-short">{{ money(payment?.remaining ?? 0) }}</span>
        </div>
      </div>
      <div class="pay-hint">Quét mã bên cạnh để chuyển nốt phần còn thiếu.</div>
      <template #actions>
        <button class="btn btn-ghost btn-md" type="button" @click="callStaff">Gọi nhân viên</button>
        <button class="btn btn-primary btn-md btn-arrowed" type="button" @click="refreshPayment">
          Đã chuyển xong
          <span class="btn-arrow"><Icon name="arrow-right" :size="20" :stroke="2.6" /></span>
        </button>
      </template>
      <template #aside>
        <img v-if="remainingQrUrl" class="notice-qr" :src="remainingQrUrl" alt="Mã chuyển phần còn thiếu" />
        <span class="mono muted">Mã phiên {{ sessionCode }}</span>
      </template>
    </NoticeDialog>

    <!-- 05c · are you still there? -->
    <NoticeDialog
      :open="stillThereOpen"
      title="Bạn còn ở đó không?"
      :text="`Chạm bất kỳ đâu để tiếp tục chọn ảnh.\nHết giờ, máy sẽ tự chọn ${store.slotCount} ảnh đầu và in cho bạn.`"
    >
      <template #badge>
        <span class="chrome-sphere still-ring">
          <svg class="still-arc" viewBox="0 0 100 100" aria-hidden="true">
            <circle
              cx="50"
              cy="50"
              r="46"
              :style="{
                strokeDashoffset:
                  289 * (1 - stillThereLeft / (store.config?.photo_select_grace_seconds ?? 15)),
              }"
            />
          </svg>
          <span class="display still-num">{{ pad2(Math.max(0, stillThereLeft)) }}</span>
        </span>
      </template>
      <template #actions>
        <button class="btn btn-primary btn-lg btn-arrowed" type="button" @click="stillHere">
          Tôi vẫn ở đây
          <span class="btn-arrow"><Icon name="arrow-right" :size="23" :stroke="2.6" /></span>
        </button>
      </template>
    </NoticeDialog>

    <!-- 07b · paying for extra print copies -->
    <NoticeDialog
      :open="copiesPayOpen"
      icon="printer"
      :title="`In thêm ${copies - 1} bản`"
      :width="paymentQrUrl ? 90 : 64"
      :text="
        paymentQrUrl
          ? 'Quét mã để thanh toán, hoặc trả tại quầy.'
          : 'Thanh toán tại quầy, nhân viên xác nhận bằng PIN.'
      "
    >
      <div class="pay-lines">
        <div>
          <span>{{ copies - 1 }} bản × {{ money(extraCopyPrice) }}</span
          ><span class="display accent pay-short">{{ money(payment?.remaining ?? 0) }}</span>
        </div>
      </div>
      <template #actions>
        <button class="btn btn-ghost btn-md" type="button" @click="cancelCopiesPayment">Chỉ in 1 bản</button>
        <button class="btn btn-dark btn-md" type="button" @click="openPin('copies')">
          <Icon name="lock" :size="22" />
          Nhân viên xác nhận · PIN
        </button>
      </template>
      <template v-if="paymentQrUrl" #aside>
        <img class="notice-qr" :src="paymentQrUrl" alt="Mã chuyển khoản in thêm" />
        <span class="mono muted">Mã phiên {{ sessionCode }}</span>
      </template>
    </NoticeDialog>

    <LoyaltyDialog
      :open="loyaltyOpen"
      :session-id="store.sessionId"
      :target="loyaltyTarget"
      @close="closeLoyalty"
      @done="openThanks"
    />

    <PinDialog
      :open="pinOpen"
      :description="pinDescription"
      :context="pinContext"
      @close="pinOpen = false"
      @success="onPinSuccess"
    />

    <Transition name="dialog">
      <div v-if="errorTitle" class="dialog-backdrop">
        <div class="dialog dialog--narrow chrome-ring" role="alertdialog" :aria-label="errorTitle">
          <div class="dialog-inner dialog-center">
            <div class="error-badge"><Icon name="alert" :size="44" :stroke="3" /></div>
            <div>
              <div class="display pin-title">{{ errorTitle }}</div>
              <div class="pin-desc">{{ errorText }}</div>
            </div>
            <div class="row-actions">
              <button class="btn btn-ghost btn-md" type="button" @click="returnToIdle()">
                <Icon name="home" :size="20" />
                Về màn chờ
              </button>
              <button
                v-if="retryAction"
                class="btn btn-primary btn-md btn-arrowed"
                type="button"
                @click="retryError"
              >
                Thử lại
                <span class="btn-arrow"><Icon name="refresh" :size="20" :stroke="2.6" /></span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <span
      v-for="tap in taps"
      :key="tap.id"
      class="tap-star"
      :style="{ left: `${tap.x}px`, top: `${tap.y}px` }"
      ><Star
    /></span>

    <div v-if="DEMO" class="demo-badge mono">Bản demo · PIN nhân viên 1234</div>

    <TransitionOverlay ref="overlay" :reduced="reduced" />
  </div>
</template>
