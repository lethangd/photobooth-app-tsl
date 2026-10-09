<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import { KIOSK, getJson, request, sendJson, type Overview, type PrinterStatus } from "../api";
import AIcon from "../components/AIcon.vue";
import { bytes } from "../format";
import { errorText, notify, refreshSummary } from "../state";

const FREE_TIER_BYTES = 10 * 1024 ** 3;
const LIVE_URL = "/api/aquisition/stream.mjpg";

const overview = ref<Overview | null>(null);
const updatedAt = ref(0);
const now = ref(Date.now());
const busy = ref("");
const live = ref(false);
const snapshotUrl = ref("");
let ticker = 0;

const printer = computed(() => overview.value?.printer.kiosk_printer ?? null);
const others = computed(() =>
  (overview.value?.printer.printers ?? []).filter((item) => item.name !== printer.value?.name),
);
const printerLevel = computed(() => {
  const severity = printer.value?.severity ?? "error";
  return severity === "ok" || severity === "info" ? "ok" : severity === "warning" ? "warn" : "err";
});
const printerBadge = computed(
  () => ({ ok: "Sẵn sàng", warn: "Cần chú ý", err: "Có lỗi" })[printerLevel.value],
);
const cloudPercent = computed(() =>
  Math.min(100, ((overview.value?.cloud.bytes ?? 0) / FREE_TIER_BYTES) * 100),
);
const updatedText = computed(() => {
  if (!updatedAt.value) return "Đang tải…";
  const seconds = Math.max(0, Math.round((now.value - updatedAt.value) / 1000));
  return seconds < 5 ? "Vừa cập nhật" : `Cập nhật ${seconds} giây trước`;
});

async function load(): Promise<void> {
  try {
    overview.value = await getJson<Overview>(`${KIOSK}/overview`);
    updatedAt.value = Date.now();
  } catch (exc) {
    notify(errorText(exc), true);
  }
}

async function run(key: string, action: () => Promise<unknown>, done: string): Promise<void> {
  if (busy.value) return;
  busy.value = key;
  try {
    await action();
    notify(done);
  } catch (exc) {
    notify(errorText(exc), true);
  } finally {
    busy.value = "";
  }
}

function testPrint(): Promise<void> {
  return run("print", () => sendJson(`${KIOSK}/printer/test`, "POST"), "Đã gửi trang in thử");
}

function usePrinter(name: string): Promise<void> {
  return run(
    `use-${name}`,
    async () => {
      const status = await sendJson<PrinterStatus>(`${KIOSK}/printer/select`, "POST", { name });
      if (overview.value) overview.value.printer = status;
      await refreshSummary();
    },
    `Kiosk sẽ in ra "${name}"`,
  );
}

function testCapture(): Promise<void> {
  return run(
    "capture",
    async () => {
      const blob = await (await request("/api/aquisition/still")).blob();
      if (snapshotUrl.value) URL.revokeObjectURL(snapshotUrl.value);
      snapshotUrl.value = URL.createObjectURL(blob);
    },
    "Đã chụp thử",
  );
}

function restartCamera(): Promise<void> {
  live.value = false;
  return run(
    "restart",
    async () => {
      await request("/api/system/service/reload");
      await load();
    },
    "Đã khởi động lại camera và các dịch vụ",
  );
}

onMounted(() => {
  void load();
  ticker = window.setInterval(() => {
    now.value = Date.now();
    if (now.value - updatedAt.value > 15000) void load();
  }, 1000);
});

onBeforeUnmount(() => {
  window.clearInterval(ticker);
  if (snapshotUrl.value) URL.revokeObjectURL(snapshotUrl.value);
});
</script>

<template>
  <div style="display: flex; flex-direction: column; gap: 20px">
    <header class="page-head">
      <div>
        <div class="kicker">{{ updatedText }}</div>
        <h1 class="h1">Máy in &amp; camera</h1>
      </div>
      <button type="button" class="btn btn-ghost" @click="load"><AIcon name="refresh" />Kiểm tra lại</button>
    </header>

    <section class="grid">
      <article
        class="card"
        aria-label="Máy in của kiosk"
        :style="{
          borderWidth: '2px',
          borderColor:
            printerLevel === 'ok' ? 'var(--line)' : printerLevel === 'warn' ? '#f0c36b' : '#f4a3ae',
          borderRadius: '28px',
          padding: '24px',
          gap: '18px',
        }"
      >
        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px">
          <div style="display: flex; gap: 14px; align-items: center; min-width: 0">
            <span class="square-icon" style="background: var(--ink); color: #fff"
              ><AIcon name="printer" :size="26"
            /></span>
            <div style="min-width: 0">
              <div class="kicker" style="font-size: 11px">Máy in của kiosk</div>
              <div
                style="
                  font-family: var(--display);
                  font-weight: 800;
                  font-size: 22px;
                  overflow-wrap: break-word;
                  word-break: normal;
                "
              >
                {{ printer?.name ?? (overview?.printer.configured_name || "Chưa chọn máy in") }}
              </div>
            </div>
          </div>
          <span class="pill" :class="printerLevel" style="font-size: 14px; padding: 8px 14px">{{
            printerBadge
          }}</span>
        </div>
        <div class="stat-row">
          <div>
            <span class="muted">Trạng thái</span
            ><strong>{{ printer ? printer.summary.split(" · ")[0] : "Không tìm thấy" }}</strong>
          </div>
          <div>
            <span class="muted">Lệnh đang chờ</span><strong>{{ printer?.jobs ?? "—" }}</strong>
          </div>
          <div>
            <span class="muted">Cổng</span><strong class="ellipsis">{{ printer?.port || "—" }}</strong>
          </div>
        </div>
        <div v-if="!printer" class="alert error" style="font-size: 14px">
          Máy in "{{ overview?.printer.configured_name }}" không có trên máy tính. Chọn một máy in bên dưới.
        </div>
        <div v-else-if="printerLevel !== 'ok'" class="alert warn" style="font-size: 14px; line-height: 1.5">
          {{ printer.flags.map((flag) => flag.label).join(", ") }}. Xử lý theo hướng dẫn của hãng máy in, sau
          đó bấm "In thử" để kiểm tra.
        </div>
        <div class="actions">
          <button
            type="button"
            class="btn btn-primary"
            style="flex: 1 1 140px"
            :disabled="!!busy"
            @click="testPrint"
          >
            {{ busy === "print" ? "Đang gửi…" : "In thử 1 tờ" }}
          </button>
          <a href="#other-printers" class="btn btn-ghost" style="flex: 1 1 140px">Đổi máy in</a>
        </div>
      </article>

      <article class="card" aria-label="Camera" style="border-radius: 28px; padding: 24px; gap: 18px">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px">
          <div style="display: flex; gap: 14px; align-items: center; min-width: 0">
            <span class="square-icon" style="background: var(--cobalt); color: #fff"
              ><AIcon name="camera" :size="26"
            /></span>
            <div style="min-width: 0">
              <div class="kicker" style="font-size: 11px">Camera chính</div>
              <div
                style="
                  font-family: var(--display);
                  font-weight: 800;
                  font-size: 22px;
                  overflow-wrap: break-word;
                  word-break: normal;
                "
              >
                {{
                  overview?.camera.device || overview?.camera.description || overview?.camera.backend || "—"
                }}
              </div>
            </div>
          </div>
          <span
            class="pill"
            :class="overview?.camera.running ? 'ok' : 'err'"
            style="font-size: 14px; padding: 8px 14px"
            >{{ overview?.camera.running ? "Hoạt động" : "Không phản hồi" }}</span
          >
        </div>
        <div class="live-box">
          <img v-if="live" :src="LIVE_URL" alt="Xem trực tiếp camera" />
          <img v-else-if="snapshotUrl" :src="snapshotUrl" alt="Ảnh chụp thử" />
          <button v-else type="button" class="btn btn-ghost btn-sm" @click="live = true">
            <AIcon name="eye" :size="18" />Xem trực tiếp
          </button>
          <button
            v-if="live || snapshotUrl"
            type="button"
            class="btn btn-ghost btn-sm live-close"
            @click="((live = false), (snapshotUrl = ''))"
          >
            Đóng
          </button>
        </div>
        <div style="display: flex; flex-direction: column; gap: 8px; font-size: 14px">
          <div style="display: flex; justify-content: space-between; gap: 10px">
            <span class="muted">Kết nối qua</span><strong>{{ overview?.camera.backend ?? "—" }}</strong>
          </div>
          <div style="display: flex; justify-content: space-between; gap: 10px">
            <span class="muted">Camera dự phòng</span>
            <strong style="text-align: right">{{
              overview?.camera.browser_fallback ? "Webcam của máy · tự bật khi camera chính lỗi" : "Đang tắt"
            }}</strong>
          </div>
        </div>
        <div class="actions">
          <button
            type="button"
            class="btn btn-dark"
            style="flex: 1 1 140px"
            :disabled="!!busy"
            @click="testCapture"
          >
            {{ busy === "capture" ? "Đang chụp…" : "Chụp thử" }}
          </button>
          <button
            type="button"
            class="btn btn-ghost"
            style="flex: 1 1 140px"
            :disabled="!!busy"
            @click="restartCamera"
          >
            {{ busy === "restart" ? "Đang khởi động…" : "Khởi động lại camera" }}
          </button>
        </div>
      </article>
    </section>

    <section class="grid">
      <div id="other-printers" class="card">
        <h2 class="h2">Máy in khác trên máy tính</h2>
        <div v-if="!others.length" class="empty">Không có máy in nào khác.</div>
        <div v-for="item in others" :key="item.name" class="row-item">
          <span
            class="dot"
            :class="
              item.severity === 'ok' || item.severity === 'info'
                ? 'ok'
                : item.severity === 'warning'
                  ? 'warn'
                  : 'err'
            "
          />
          <div class="grow">
            <div style="font-weight: 700; overflow-wrap: break-word; word-break: normal">{{ item.name }}</div>
            <div class="sub">
              {{ item.name === overview?.printer.default_name ? "Mặc định của Windows · " : ""
              }}{{ item.summary }}
            </div>
          </div>
          <button
            type="button"
            class="btn btn-ghost btn-sm"
            :disabled="!!busy"
            @click="usePrinter(item.name)"
          >
            Dùng máy này
          </button>
        </div>
      </div>
      <div class="card">
        <h2 class="h2">Lưu trữ ảnh số</h2>
        <div style="display: flex; align-items: center; gap: 12px">
          <span
            class="dot"
            :class="overview?.cloud.available ? 'ok' : overview?.cloud.enabled ? 'warn' : 'off'"
          />
          <strong>{{
            overview?.cloud.available
              ? `Cloudflare R2 · đã kết nối`
              : overview?.cloud.enabled
                ? "Chưa kết nối R2 (thiếu file .env.r2)"
                : "Đang tắt"
          }}</strong>
        </div>
        <div v-if="overview?.cloud.available">
          <div style="display: flex; justify-content: space-between; font-size: 14px; margin-bottom: 8px">
            <span class="muted">Dung lượng gói miễn phí</span
            ><strong>{{ bytes(overview.cloud.bytes) }} / 10 GB</strong>
          </div>
          <div class="meter">
            <i :style="{ width: `${Math.max(1, cloudPercent)}%`, background: 'var(--cobalt)' }" />
          </div>
        </div>
        <div class="muted" style="font-size: 14px; line-height: 1.5">
          {{ overview?.cloud.objects ?? 0 }} file trên cloud. Ảnh tự xoá sau
          {{ overview?.cloud.retention_days ?? 7 }} ngày.
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.stat-row {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.stat-row > div {
  background: var(--panel);
  border-radius: 18px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  padding: 14px;
}
.stat-row span {
  font-size: 13px;
}
.ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.live-box {
  align-items: center;
  background: #2b2530;
  border-radius: 20px;
  display: flex;
  height: 220px;
  justify-content: center;
  overflow: hidden;
  position: relative;
}
.live-box img {
  height: 100%;
  object-fit: cover;
  width: 100%;
}
.live-close {
  position: absolute;
  right: 10px;
  top: 10px;
}
@media (max-width: 520px) {
  .stat-row {
    grid-template-columns: 1fr;
  }
}
</style>
