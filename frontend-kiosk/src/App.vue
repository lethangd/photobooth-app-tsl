<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { toDataURL } from "qrcode";

import {
  LIVE_STREAM_URL,
  capture,
  compositePreview,
  renderCollage,
  renderTimelapse,
  templatePreviewUrl,
} from "@/api/framebooth";
import type { CaptureResult, FrameTemplateSummary } from "@/api/types";
import Confetti from "@/components/Confetti.vue";
import Icon from "@/components/Icon.vue";
import { useSessionStore } from "@/stores/session";

type Screen =
  | "loading"
  | "idle"
  | "package"
  | "payment"
  | "ready"
  | "capturing"
  | "photoSelect"
  | "filter"
  | "final"
  | "printing"
  | "qr"
  | "thankYou";

const STEPS = ["Chọn khung", "Thanh toán", "Chụp ảnh", "Chọn ảnh", "Màu & viền", "Nhận ảnh"];
const STEP_OF_SCREEN: Partial<Record<Screen, number>> = {
  package: 0,
  payment: 1,
  ready: 2,
  capturing: 2,
  photoSelect: 3,
  filter: 4,
  final: 5,
  printing: 5,
  qr: 5,
};
const NO_TIMEOUT_BAR: Screen[] = ["loading", "idle", "capturing"];

const store = useSessionStore();

const screen = ref<Screen>("loading");
const captureRunId = ref(0);
const currentShot = ref(0);
const countdown = ref(0);
const captureStatus = ref("Tạo dáng nào!");
const designPreviewUrl = ref("");
const finalPreviewUrl = ref("");
const paymentQrUrl = ref("");
const resultQrUrl = ref("");
const timelapseUrl = ref("");
const timelapseId = ref<string | null>(null);
const timelapseDone = ref(false);
const printDone = ref(false);
const errorTitle = ref("");
const errorText = ref("");
const retryAction = ref<(() => void) | null>(null);
const flashOn = ref(false);
const isPrinting = ref(false);

// drives the thin "auto-continue" bar at the bottom of the screen
const timerNonce = ref(0);
const timerSeconds = ref(0);

const timers: number[] = [];
const urlCache = new Map<string, string>();

const SPARKLES = Array.from({ length: 22 }, (_, i) => {
  const rand = (n: number) => {
    const x = Math.sin(i * 12.9898 + n * 78.233) * 43758.5453;
    return x - Math.floor(x);
  };
  return {
    "--x": `${rand(1) * 100}%`,
    "--y": `${rand(2) * 100}%`,
    "--s": `${2 + rand(3) * 4}px`,
    "--d": `${3 + rand(4) * 4}s`,
    "--delay": `${-rand(5) * 6}s`,
  };
});

const heroTemplates = computed(() =>
  (store.config?.frame_types ?? [])
    .map((frameType) => frameType.templates[0])
    .filter((template): template is FrameTemplateSummary => Boolean(template)),
);
const selectedPackage = computed(() => store.packageConfig);
const selectedCaptureSet = computed(() => new Set(store.selectedCaptureIds));
const stepIndex = computed(() => STEP_OF_SCREEN[screen.value] ?? -1);
const showTimeoutBar = computed(() => !NO_TIMEOUT_BAR.includes(screen.value) && timerSeconds.value > 0);
const retentionDays = computed(
  () => store.finalResult?.retention_days ?? store.config?.digital_delivery_retention_days ?? 7,
);

function money(value: number): string {
  return `${new Intl.NumberFormat("vi-VN").format(value)}đ`;
}

/** Cache-busted URL, stable across re-renders so images do not reload every countdown tick. */
function stableUrl(url: string): string {
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

function clearTimers(): void {
  while (timers.length > 0) {
    const timer = timers.pop();
    if (timer !== undefined) window.clearTimeout(timer);
  }
  timerSeconds.value = 0;
}

function setTimer(callback: () => void, seconds: number): void {
  const safe = Math.max(0, seconds);
  timers.push(window.setTimeout(callback, safe * 1000));
  timerSeconds.value = safe;
  timerNonce.value += 1;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function revokePreviewUrls(): void {
  if (designPreviewUrl.value.startsWith("blob:")) URL.revokeObjectURL(designPreviewUrl.value);
  if (finalPreviewUrl.value.startsWith("blob:")) URL.revokeObjectURL(finalPreviewUrl.value);
  designPreviewUrl.value = "";
  finalPreviewUrl.value = "";
  timelapseUrl.value = "";
  timelapseId.value = null;
}

function go(next: Screen): void {
  clearTimers();
  screen.value = next;
}

async function makeQr(value: string): Promise<string> {
  return await toDataURL(value, {
    width: 640,
    margin: 1,
    color: { dark: "#111318", light: "#ffffff" },
  });
}

function showError(title: string, text: unknown, retry?: () => void): void {
  errorTitle.value = title;
  errorText.value = text instanceof Error ? text.message : String(text);
  retryAction.value = retry ?? null;
}

function hideError(): void {
  errorTitle.value = "";
  errorText.value = "";
  retryAction.value = null;
}

async function resetSession(): Promise<void> {
  clearTimers();
  captureRunId.value += 1;
  revokePreviewUrls();
  urlCache.clear();
  store.resetSession();
  store.setFinalResult(null);
  paymentQrUrl.value = "";
  resultQrUrl.value = "";
  timelapseDone.value = false;
  printDone.value = false;
  isPrinting.value = false;
  hideError();
  go("idle");
}

function startPackageSelect(): void {
  hideError();
  go("package");
  setTimer(() => void resetSession(), store.config?.package_select_timeout_seconds ?? 30);
}

async function selectPackage(slotCount: number): Promise<void> {
  store.selectPackage(slotCount);
  const amount = store.packageConfig?.price ?? 0;
  paymentQrUrl.value = await makeQr(`VIETQR:TSL:${store.sessionId}:${amount}`);
  go("payment");
  setTimer(showReady, store.config?.payment_mock_seconds ?? 3);
}

function showReady(): void {
  go("ready");
  setTimer(() => void startCaptureSequence(), store.config?.get_ready_seconds ?? 3);
}

function triggerFlash(): void {
  flashOn.value = false;
  window.requestAnimationFrame(() => {
    flashOn.value = true;
    window.setTimeout(() => {
      flashOn.value = false;
    }, 620);
  });
}

async function runCountdown(seconds: number, runId: number): Promise<boolean> {
  countdown.value = seconds;
  captureStatus.value = "Tạo dáng nào!";
  for (let remaining = seconds; remaining > 0; remaining -= 1) {
    if (captureRunId.value !== runId) return false;
    countdown.value = remaining;
    if (remaining <= 2) captureStatus.value = "Cười thật tươi!";
    await sleep(1000);
  }
  countdown.value = 0;
  return captureRunId.value === runId;
}

async function startCaptureSequence(): Promise<void> {
  const config = store.config;
  const packageConfig = store.packageConfig;
  if (!config || !packageConfig) {
    showError("Chưa chọn khung", "Hãy chọn khung ảnh trước khi chụp.", startPackageSelect);
    return;
  }

  const runId = captureRunId.value + 1;
  captureRunId.value = runId;
  store.clearCaptures();
  go("capturing");

  try {
    for (let shot = 1; shot <= packageConfig.shots_to_take; shot += 1) {
      currentShot.value = shot;
      if (!(await runCountdown(config.countdown_seconds, runId))) return;
      captureStatus.value = "Đang chụp…";
      triggerFlash();
      const captured = await capture();
      if (captureRunId.value !== runId) return;
      store.addCapture(captured);
      captureStatus.value = shot === packageConfig.shots_to_take ? "Xong rồi!" : "Đẹp lắm!";
      await sleep(600);
    }
    go("photoSelect");
    setTimer(autoSelectPhotosAndFilter, config.photo_select_warn_seconds + config.photo_select_grace_seconds);
  } catch (error) {
    showError("Camera chưa phản hồi", error, () => void startCaptureSequence());
  }
}

function retake(): void {
  store.clearCaptures();
  void startCaptureSequence();
}

function toggleCaptureSelection(captureItem: CaptureResult): void {
  store.toggleCaptureSelection(captureItem.id);
  clearTimers();
  setTimer(
    autoSelectPhotosAndFilter,
    (store.config?.photo_select_warn_seconds ?? 45) + (store.config?.photo_select_grace_seconds ?? 15),
  );
}

function autoSelectPhotosAndFilter(): void {
  if (!store.hasExactSelection) store.autoSelectFirstN();
  void showFilterSelect();
}

async function showFilterSelect(): Promise<void> {
  if (!store.hasExactSelection) return;
  store.ensureTemplateSelected();
  go("filter");
  await refreshDesignPreview();
  setTimer(
    () => void showResultScreen(),
    (store.config?.filter_select_warn_seconds ?? 45) + (store.config?.filter_select_grace_seconds ?? 10),
  );
}

async function refreshDesignPreview(): Promise<void> {
  const template = store.selectedTemplate;
  if (!template || store.selectedCaptureIds.length === 0) return;
  try {
    const blob = await compositePreview(template.id, store.selectedCaptureIds, store.filterId);
    if (designPreviewUrl.value.startsWith("blob:")) URL.revokeObjectURL(designPreviewUrl.value);
    designPreviewUrl.value = URL.createObjectURL(blob);
  } catch (error) {
    console.warn(error);
    designPreviewUrl.value = template.preview_url;
  }
}

async function selectFilter(filterId: string): Promise<void> {
  store.selectFilter(filterId);
  await refreshDesignPreview();
}

async function selectTemplate(templateId: string): Promise<void> {
  store.selectTemplate(templateId);
  await refreshDesignPreview();
}

async function startTimelapseRender(): Promise<void> {
  timelapseDone.value = false;
  if (!store.digitalDeliveryEnabled || store.captures.length < 2) return;

  try {
    const result = await renderTimelapse({
      capture_ids: store.captures.map((captureItem) => captureItem.id),
      filter_id: store.filterId,
      session_id: store.sessionId,
    });
    timelapseId.value = result.id;
    timelapseUrl.value = stableUrl(result.video_url);
    timelapseDone.value = true;
  } catch (error) {
    console.warn(error);
  }
}

async function showResultScreen(): Promise<void> {
  const template = store.selectedTemplate;
  if (!template || !store.hasExactSelection) {
    showError("Thiếu ảnh hoặc khung", "Hãy chọn đủ ảnh rồi thử lại.", () => void showFilterSelect());
    return;
  }

  go("final");
  await refreshDesignPreview();
  if (finalPreviewUrl.value.startsWith("blob:")) URL.revokeObjectURL(finalPreviewUrl.value);
  finalPreviewUrl.value = designPreviewUrl.value;
  designPreviewUrl.value = "";
  void startTimelapseRender();
  setTimer(() => void printFinal(), store.config?.final_preview_timeout_seconds ?? 30);
}

async function printFinal(): Promise<void> {
  const template = store.selectedTemplate;
  if (!template || isPrinting.value) return;

  isPrinting.value = true;
  printDone.value = false;
  go("printing");

  try {
    const result = await renderCollage({
      template_id: template.id,
      capture_ids: store.selectedCaptureIds,
      all_capture_ids: store.captures.map((captureItem) => captureItem.id),
      filter_id: store.filterId,
      session_id: store.sessionId,
      digital_delivery: store.digitalDeliveryEnabled,
      timelapse_id: timelapseId.value,
    });
    store.setFinalResult(result);
    const downloadUrl =
      result.cloud_url ?? `${window.location.origin}${result.download_url || result.gallery_url}`;
    resultQrUrl.value = await makeQr(downloadUrl);
    printDone.value = true;
  } catch (error) {
    showError("Chưa in được ảnh", error, () => void printFinal());
  } finally {
    isPrinting.value = false;
    setTimer(showQrDownload, store.config?.printing_mock_seconds ?? 4);
  }
}

function showQrDownload(): void {
  go("qr");
  setTimer(showThankYou, store.config?.qr_download_seconds ?? 18);
}

function showThankYou(): void {
  go("thankYou");
  setTimer(() => void resetSession(), store.config?.thank_you_seconds ?? 5);
}

function retryError(): void {
  const retry = retryAction.value;
  hideError();
  retry?.();
}

onMounted(async () => {
  try {
    await store.loadConfig();
    await resetSession();
  } catch (error) {
    screen.value = "idle";
    showError("Không tải được kiosk", error, () => window.location.reload());
  }
});

onBeforeUnmount(() => {
  clearTimers();
  revokePreviewUrls();
});
</script>

<template>
  <div class="app" :data-screen="screen">
    <div class="aurora" aria-hidden="true">
      <div class="blob blob--a" />
      <div class="blob blob--b" />
      <div class="blob blob--c" />
      <div class="sparkles">
        <i v-for="(sparkle, index) in SPARKLES" :key="index" :style="sparkle" />
      </div>
    </div>
    <div class="vignette" aria-hidden="true" />

    <header class="topbar">
      <div class="brand">
        <span class="brand-mark">TSL</span>
        <span>Photobooth</span>
      </div>
      <nav class="stepper" :class="{ show: stepIndex >= 0 }" aria-hidden="true">
        <div
          v-for="(label, index) in STEPS"
          :key="label"
          class="step"
          :class="{ done: index < stepIndex, active: index === stepIndex }"
        >
          <span>{{ label }}</span>
        </div>
      </nav>
      <div class="topbar-end">
        <span v-if="stepIndex >= 0" class="session-pill">{{ store.sessionId }}</span>
      </div>
    </header>

    <Transition name="screen" mode="out-in">
      <!-- ───────── loading ───────── -->
      <main v-if="screen === 'loading'" key="loading" class="screen">
        <div class="loader" />
      </main>

      <!-- ───────── idle ───────── -->
      <main v-else-if="screen === 'idle'" key="idle" class="screen idle" @click="startPackageSelect">
        <h1 class="title rise grad-text" style="--i: 0">Lưu giữ<br />khoảnh khắc</h1>

        <div class="idle-hero">
          <div
            v-for="(template, index) in heroTemplates"
            :key="template.id"
            class="hero-frame rise"
            :style="{ '--rot': `${[-7, 0, 7][index % 3]}deg`, '--i': index + 1 }"
          >
            <img :alt="template.name" :src="templateImage(template)" />
          </div>
        </div>

        <div class="cta-wrap rise" style="--i: 4">
          <button class="btn btn-primary btn-xl" type="button">
            <Icon name="touch" :size="32" />
            Chạm để bắt đầu
          </button>
        </div>
      </main>

      <!-- ───────── package ───────── -->
      <main v-else-if="screen === 'package'" key="package" class="screen">
        <h1 class="title title--md rise" style="--i: 0">Chọn khung ảnh</h1>

        <div class="package-grid">
          <button
            v-for="(frameType, index) in store.config?.frame_types"
            :key="frameType.slot_count"
            class="package-card glass rise"
            :style="{ '--i': index + 1 }"
            type="button"
            @click="selectPackage(frameType.slot_count)"
          >
            <div class="package-image">
              <img
                v-if="frameType.templates[0]"
                :alt="`${frameType.slot_count} ảnh`"
                :src="templateImage(frameType.templates[0])"
              />
            </div>
            <div class="package-body">
              <div class="package-count">{{ frameType.slot_count }} ảnh</div>
              <div class="package-price">{{ money(frameType.price) }}</div>
            </div>
          </button>
        </div>

        <button
          class="digital-toggle glass rise"
          :class="{ active: store.digitalDeliveryEnabled }"
          style="--i: 5"
          type="button"
          @click="store.toggleDigitalDelivery"
        >
          <span class="switch" aria-hidden="true"><span /></span>
          <span>
            <strong>Ảnh số + video qua QR</strong>
            <small>{{ store.digitalDeliveryEnabled ? "Đang bật" : "Đang tắt" }}</small>
          </span>
        </button>
      </main>

      <!-- ───────── payment ───────── -->
      <main v-else-if="screen === 'payment'" key="payment" class="screen">
        <div class="split">
          <div class="split-copy">
            <h1 class="title title--md title--left rise" style="--i: 0">Quét mã<br />để thanh toán</h1>
            <div class="actions rise" style="--i: 2">
              <button class="btn btn-ghost" type="button" @click="startPackageSelect">
                <Icon name="arrow-left" />
                Đổi khung
              </button>
              <button class="btn btn-primary" type="button" @click="showReady">
                <Icon name="check" />
                Đã thanh toán
              </button>
            </div>
          </div>
          <div class="qr-card rise" style="--i: 1">
            <img v-if="paymentQrUrl" alt="Mã thanh toán" :src="paymentQrUrl" />
            <div class="qr-amount">{{ selectedPackage ? money(selectedPackage.price) : "" }}</div>
          </div>
        </div>
      </main>

      <!-- ───────── ready ───────── -->
      <main v-else-if="screen === 'ready'" key="ready" class="screen">
        <div class="live rise" style="--i: 0">
          <img alt="Camera" :src="LIVE_STREAM_URL" />
          <div class="live-guide" />
          <div class="live-bottom">
            <h1 class="title title--md">Sẵn sàng chưa?</h1>
            <p class="lead" style="margin-top: 0">Đứng vào giữa khung hình</p>
            <div class="bar-ready">
              <span :style="{ animationDuration: `${store.config?.get_ready_seconds ?? 3}s` }" />
            </div>
            <button class="btn btn-primary" type="button" @click="startCaptureSequence">
              <Icon name="camera" />
              Chụp ngay
            </button>
          </div>
        </div>
      </main>

      <!-- ───────── capturing ───────── -->
      <main v-else-if="screen === 'capturing'" key="capturing" class="screen">
        <div class="live">
          <img alt="Camera" :src="LIVE_STREAM_URL" />

          <div class="chip chip--tl">
            <Icon name="camera" :size="22" />
            {{ currentShot }} / {{ store.shotsToTake }}
          </div>
          <div v-if="store.digitalDeliveryEnabled" class="chip chip--tr"><span class="rec-dot" />REC</div>

          <div class="countdown">
            <div class="count-stage">
              <svg class="count-ring" viewBox="0 0 100 100" aria-hidden="true">
                <defs>
                  <linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0%" stop-color="#ff3d81" />
                    <stop offset="100%" stop-color="#7c4dff" />
                  </linearGradient>
                </defs>
                <circle class="track" cx="50" cy="50" r="44" />
                <circle v-if="countdown > 0" :key="countdown" class="bar" cx="50" cy="50" r="44" />
              </svg>
              <div v-if="countdown > 0" :key="countdown" class="count-num">{{ countdown }}</div>
              <Icon v-else class="count-icon" name="camera" :size="110" />
            </div>
            <div class="count-caption">{{ captureStatus }}</div>
          </div>

          <div class="shot-strip">
            <div
              v-for="slot in store.shotsToTake"
              :key="slot"
              class="shot-slot"
              :class="{ filled: store.captures[slot - 1] }"
            >
              <img
                v-if="store.captures[slot - 1]"
                alt=""
                :src="stableUrl(store.captures[slot - 1].preview_url)"
              />
            </div>
          </div>

          <div class="flash" :class="{ on: flashOn }" />
        </div>
      </main>

      <!-- ───────── photo select ───────── -->
      <main v-else-if="screen === 'photoSelect'" key="photoSelect" class="screen">
        <div class="head rise" style="--i: 0">
          <h1 class="title title--md">Chọn {{ store.slotCount }} ảnh đẹp nhất</h1>
          <div class="count-chip">
            <i v-for="n in store.slotCount" :key="n" :class="{ on: n <= store.selectedCaptureIds.length }" />
          </div>
        </div>

        <div class="photo-grid">
          <button
            v-for="(captureItem, index) in store.captures"
            :key="captureItem.id"
            class="photo-card rise"
            :class="{
              selected: selectedCaptureSet.has(captureItem.id),
              full: store.hasExactSelection,
            }"
            :style="{ '--i': index + 1 }"
            type="button"
            @click="toggleCaptureSelection(captureItem)"
          >
            <img :alt="`Ảnh ${index + 1}`" :src="stableUrl(captureItem.preview_url)" />
            <span
              v-if="selectedCaptureSet.has(captureItem.id)"
              :key="`b${captureItem.id}`"
              class="select-badge"
            >
              {{ store.selectedCaptureIds.indexOf(captureItem.id) + 1 }}
            </span>
          </button>
        </div>

        <div class="actions footer-actions rise" style="--i: 6">
          <button class="btn btn-ghost" type="button" @click="retake">
            <Icon name="refresh" />
            Chụp lại
          </button>
          <button
            class="btn btn-primary"
            type="button"
            :disabled="!store.hasExactSelection"
            @click="showFilterSelect"
          >
            Tiếp tục
            <Icon name="arrow-right" />
          </button>
        </div>
      </main>

      <!-- ───────── filter ───────── -->
      <main v-else-if="screen === 'filter'" key="filter" class="screen">
        <div class="design">
          <div class="preview-stage rise" style="--i: 0">
            <div class="preview-paper">
              <div v-if="!designPreviewUrl" class="skeleton" />
              <img v-if="designPreviewUrl" alt="Xem trước" :src="designPreviewUrl" />
            </div>
          </div>

          <div class="controls glass rise" style="--i: 1">
            <div>
              <div class="control-title"><Icon name="sparkle" :size="18" />Màu ảnh</div>
              <div class="pick-row">
                <button
                  v-for="filter in store.config?.filters"
                  :key="filter.id"
                  class="pick"
                  :class="{ selected: filter.id === store.filterId }"
                  type="button"
                  @click="selectFilter(filter.id)"
                >
                  <span v-if="filter.id === store.filterId" class="pick-check"
                    ><Icon name="check" :size="16"
                  /></span>
                  <div class="pick-thumb">
                    <img
                      v-if="store.selectedCaptures[0]"
                      :alt="filter.name"
                      :src="stableUrl(store.selectedCaptures[0].preview_url)"
                      :style="{ filter: filter.css_filter }"
                    />
                  </div>
                  <div class="pick-name">{{ filter.name }}</div>
                </button>
              </div>
            </div>

            <div>
              <div class="control-title"><Icon name="image" :size="18" />Viền</div>
              <div class="pick-row">
                <button
                  v-for="template in store.templatesForPackage"
                  :key="template.id"
                  class="pick pick--frame"
                  :class="{ selected: template.id === store.selectedTemplateId }"
                  type="button"
                  @click="selectTemplate(template.id)"
                >
                  <span v-if="template.id === store.selectedTemplateId" class="pick-check"
                    ><Icon name="check" :size="16"
                  /></span>
                  <div class="pick-thumb"><img :alt="template.name" :src="templateImage(template)" /></div>
                  <div class="pick-name">{{ template.name }}</div>
                </button>
              </div>
            </div>

            <div class="actions" style="justify-content: flex-start">
              <button class="btn btn-ghost" type="button" @click="go('photoSelect')">
                <Icon name="arrow-left" />
                Đổi ảnh
              </button>
              <button class="btn btn-primary" type="button" @click="showResultScreen">
                Xem kết quả
                <Icon name="arrow-right" />
              </button>
            </div>
          </div>
        </div>
      </main>

      <!-- ───────── final ───────── -->
      <main v-else-if="screen === 'final'" key="final" class="screen">
        <div class="final">
          <div class="final-photo">
            <div class="final-paper">
              <img v-if="finalPreviewUrl" alt="Ảnh hoàn thiện" :src="finalPreviewUrl" />
            </div>
          </div>

          <div class="final-side">
            <h1 class="title title--md title--left rise" style="--i: 1">Đẹp quá!</h1>

            <div v-if="store.digitalDeliveryEnabled" class="video-card glass rise" style="--i: 2">
              <video v-if="timelapseUrl" :src="timelapseUrl" autoplay loop muted playsinline />
              <div v-else class="video-wait">
                <div class="loader" />
                Đang dựng video
              </div>
              <span v-if="timelapseUrl" class="video-badge"><Icon name="video" :size="16" />Timelapse</span>
            </div>

            <div class="actions rise" style="--i: 3">
              <button class="btn btn-primary btn-xl" type="button" @click="printFinal">
                <Icon name="printer" :size="30" />
                In ảnh
              </button>
              <button class="btn btn-ghost" type="button" @click="showFilterSelect">
                <Icon name="sparkle" />
                Đổi màu
              </button>
            </div>
          </div>
        </div>
      </main>

      <!-- ───────── printing ───────── -->
      <main v-else-if="screen === 'printing'" key="printing" class="screen">
        <h1 class="title title--md rise" style="--i: 0">Đang in ảnh…</h1>
        <div class="printer rise" style="--i: 1">
          <div class="printer-body"><span class="printer-led" /></div>
          <div class="printer-slot">
            <img v-if="finalPreviewUrl" class="printer-photo" alt="" :src="finalPreviewUrl" />
          </div>
        </div>
        <div class="meter"><span :style="{ transform: `scaleX(${printDone ? 1 : 0.6})` }" /></div>
      </main>

      <!-- ───────── qr ───────── -->
      <main v-else-if="screen === 'qr'" key="qr" class="screen">
        <Confetti />
        <div class="split">
          <div class="split-copy">
            <h1 class="title title--md title--left rise" style="--i: 0">
              {{ store.digitalDeliveryEnabled ? "Quét để nhận ảnh" : "Nhớ lấy ảnh nhé!" }}
            </h1>
            <p v-if="store.digitalDeliveryEnabled" class="lead lead--left rise" style="--i: 1">
              Ảnh gốc, ảnh ghép và video · giữ {{ retentionDays }} ngày
            </p>
            <div class="actions rise" style="--i: 2">
              <button class="btn btn-primary" type="button" @click="showThankYou">
                <Icon name="check" />
                Xong
              </button>
            </div>
          </div>
          <div v-if="store.digitalDeliveryEnabled" class="qr-card rise" style="--i: 1">
            <img v-if="resultQrUrl" alt="QR nhận ảnh" :src="resultQrUrl" />
          </div>
        </div>
      </main>

      <!-- ───────── thank you ───────── -->
      <main v-else key="thank-you" class="screen">
        <Confetti />
        <div class="heart rise" style="--i: 0"><Icon name="heart" :size="64" /></div>
        <h1 class="title rise grad-text" style="--i: 1; margin-top: clamp(14px, 3vh, 36px)">Cảm ơn bạn!</h1>
        <p class="lead rise" style="--i: 2">Hẹn gặp lại nhé</p>
      </main>
    </Transition>

    <div v-if="showTimeoutBar" :key="timerNonce" class="timeout-bar">
      <span :style="{ animationDuration: `${timerSeconds}s` }" />
    </div>

    <Transition name="error-fade">
      <div v-if="errorTitle" class="error-panel">
        <div class="error-box glass">
          <div class="error-icon"><Icon name="alert" :size="38" /></div>
          <h2 class="title title--md" style="font-size: clamp(26px, 4vmin, 44px)">{{ errorTitle }}</h2>
          <p>{{ errorText }}</p>
          <div class="actions">
            <button v-if="retryAction" class="btn btn-primary" type="button" @click="retryError">
              <Icon name="refresh" />
              Thử lại
            </button>
            <button class="btn btn-ghost" type="button" @click="resetSession">
              <Icon name="home" />
              Về màn chờ
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>
