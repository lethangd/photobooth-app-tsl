<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import { KIOSK, downloadFile, getJson, request, sendJson, type MulticamInfo } from "../api";
import AIcon from "../components/AIcon.vue";
import { errorText, notify } from "../state";

const BOARD = { squares_x: 14, squares_y: 9, square_length_mm: 20, marker_length_mm: 15 };
const TARGET_SHOTS = 10;

const info = ref<MulticamInfo | null>(null);
// one list of captured calibration files per camera: filess[camera][shot]
const filess = ref<string[][]>([]);
const busy = ref("");
const resultUrl = ref("");

const shots = computed(() => filess.value[0]?.length ?? 0);
const step = computed(() => (!info.value?.configured ? 1 : info.value.calibrated ? 3 : 2));

async function load(): Promise<void> {
  try {
    info.value = await getJson<MulticamInfo>(`${KIOSK}/multicam`);
  } catch (exc) {
    notify(errorText(exc), true);
  }
}

async function run(key: string, action: () => Promise<void>): Promise<void> {
  if (busy.value) return;
  busy.value = key;
  try {
    await action();
  } catch (exc) {
    notify(errorText(exc), true);
  } finally {
    busy.value = "";
  }
}

function downloadBoard(): Promise<void> {
  return run("board", () =>
    downloadFile("/api/admin/multicamera/calibration/charuco", "bang-charuco.png", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(BOARD),
    }),
  );
}

function captureShot(): Promise<void> {
  return run("shot", async () => {
    const files = await getJson<string[]>("/api/aquisition/multicam");
    const next = files.map((file, camera) => [...(filess.value[camera] ?? []), file]);
    filess.value = next;
    notify(`Đã chụp lần ${shots.value} (${files.length} camera)`);
  });
}

function calibrate(): Promise<void> {
  return run("calibrate", async () => {
    await sendJson("/api/admin/multicamera/calibration", "POST", {
      filess_in: filess.value,
      board_definition: BOARD,
    });
    notify("Đã hiệu chỉnh xong, kết quả được áp dụng ngay");
    filess.value = [];
    await load();
  });
}

function clearCalibration(): Promise<void> {
  return run("clear", async () => {
    await request("/api/admin/multicamera/calibration", { method: "DELETE" });
    notify("Đã xoá hiệu chỉnh cũ");
    await load();
  });
}

function makePreview(): Promise<void> {
  return run("preview", async () => {
    const blob = await (await request("/api/admin/multicamera/result")).blob();
    if (resultUrl.value) URL.revokeObjectURL(resultUrl.value);
    resultUrl.value = URL.createObjectURL(blob);
  });
}

onMounted(() => void load());
onBeforeUnmount(() => {
  if (resultUrl.value) URL.revokeObjectURL(resultUrl.value);
});
</script>

<template>
  <div style="display: flex; flex-direction: column; gap: 20px">
    <header class="page-head">
      <div>
        <div class="kicker">Ảnh 3D chuyển động (wigglegram)</div>
        <h1 class="h1">Multicamera</h1>
      </div>
      <span
        class="pill"
        :class="!info?.configured ? 'muted' : info.calibrated ? 'ok' : 'warn'"
        style="font-size: 14px; padding: 10px 16px"
      >
        {{ !info?.configured ? "Chưa cấu hình" : info.calibrated ? "Đã hiệu chỉnh" : "Chưa hiệu chỉnh" }}
      </span>
    </header>

    <ol class="steps" aria-label="Các bước">
      <li
        v-for="(label, index) in ['Kết nối camera', 'Hiệu chỉnh', 'Xem thử']"
        :key="label"
        :class="{ done: index + 1 < step, current: index + 1 === step }"
      >
        <span class="step-num">{{ index + 1 < step ? "✓" : index + 1 }}</span>
        <span style="font-weight: 800">{{ index + 1 }} · {{ label }}</span>
      </li>
    </ol>

    <div v-if="info && !info.configured" class="alert warn">
      <span class="alert-icon">!</span>
      <span class="alert-body">
        <strong>Chưa có hệ camera Wigglecam</strong>
        <span
          >Multicamera cần 2–4 camera nối qua mạng (Wigglecam). Thêm chúng trong phần cấu hình camera nâng
          cao, rồi quay lại đây để hiệu chỉnh.</span
        >
      </span>
      <a href="/classic#/admin/config" target="_blank" rel="noopener" class="btn btn-ghost btn-sm"
        >Mở cấu hình camera ↗</a
      >
    </div>

    <section class="split">
      <div class="card narrow">
        <h2 class="h2">Các camera (node)</h2>
        <div v-if="!info?.nodes.length" class="empty">Chưa có camera nào.</div>
        <div v-for="node in info?.nodes ?? []" :key="node.index" class="row-item">
          <span class="node-index mono">{{ node.index }}</span>
          <div class="grow">
            <div style="font-weight: 700">{{ node.description || `Camera ${node.index}` }}</div>
            <div class="mono sub">{{ node.address }}</div>
          </div>
          <span class="pill muted">Đã cấu hình</span>
        </div>
      </div>

      <div class="card wide" style="border: 2px solid var(--cobalt)">
        <h2 class="h2" style="font-size: 20px">Bước 2 · Hiệu chỉnh để các ảnh khớp nhau</h2>
        <ol
          style="
            margin: 0;
            padding-left: 22px;
            display: flex;
            flex-direction: column;
            gap: 8px;
            font-size: 15px;
            line-height: 1.5;
          "
        >
          <li>In bảng ô cờ ChArUco (khổ A4, giữ nguyên tỉ lệ).</li>
          <li>Đặt bảng ở vị trí khách sẽ đứng, sao cho mọi camera đều thấy.</li>
          <li>Chụp 5–10 lần, mỗi lần nghiêng bảng một góc khác nhau.</li>
          <li>Bấm "Tính hiệu chỉnh". Kết quả được lưu và áp dụng ngay.</li>
        </ol>
        <div class="actions" style="gap: 14px">
          <div class="board-thumb" aria-hidden="true" />
          <div style="display: flex; flex-direction: column; gap: 8px">
            <button type="button" class="btn btn-dark" :disabled="!!busy" @click="downloadBoard">
              {{ busy === "board" ? "Đang tạo…" : "Tải bảng ChArUco" }}
            </button>
            <span class="muted" style="font-size: 13px"
              >{{ BOARD.squares_x }} × {{ BOARD.squares_y }} ô · ô {{ BOARD.square_length_mm }} mm · mã
              {{ BOARD.marker_length_mm }} mm</span
            >
          </div>
        </div>
        <div>
          <div style="display: flex; justify-content: space-between; font-size: 14px; margin-bottom: 8px">
            <span style="font-weight: 700">Ảnh hiệu chỉnh đã chụp</span
            ><strong>{{ shots }} / {{ TARGET_SHOTS }}</strong>
          </div>
          <div class="shot-grid">
            <span
              v-for="index in TARGET_SHOTS"
              :key="index"
              class="shot"
              :class="{ taken: index <= shots }"
            />
          </div>
        </div>
        <div class="actions">
          <button
            type="button"
            class="btn btn-ghost"
            style="flex: 1 1 160px"
            :disabled="!!busy || !info?.configured"
            @click="captureShot"
          >
            <AIcon name="camera" />{{ busy === "shot" ? "Đang chụp…" : "Chụp ảnh hiệu chỉnh" }}
          </button>
          <button
            type="button"
            class="btn btn-primary"
            style="flex: 1 1 160px"
            :disabled="!!busy || shots < 3"
            @click="calibrate"
          >
            {{ busy === "calibrate" ? "Đang tính…" : "Tính hiệu chỉnh" }}
          </button>
        </div>
        <button
          v-if="info?.calibrated"
          type="button"
          class="btn-link"
          style="align-self: flex-start; color: #b4142a"
          :disabled="!!busy"
          @click="clearCalibration"
        >
          Xoá hiệu chỉnh cũ
        </button>
      </div>
    </section>

    <section class="card" style="flex-direction: row; flex-wrap: wrap; gap: 20px; align-items: center">
      <div class="result-box">
        <img v-if="resultUrl" :src="resultUrl" alt="Wigglegram thử" />
        <span v-else class="mono">Chưa có ảnh thử</span>
      </div>
      <div style="flex: 1 1 280px; display: flex; flex-direction: column; gap: 10px">
        <h2 class="h2">Bước 3 · Xem thử</h2>
        <span class="muted" style="font-size: 14px"
          >Mỗi khung chạy {{ info?.frame_duration_ms ?? 125 }} ms. Wigglegram đẹp nhất trong khoảng 100–200
          ms; đổi trong cấu hình nâng cao.</span
        >
      </div>
      <button type="button" class="btn btn-dark" :disabled="!!busy || !info?.configured" @click="makePreview">
        {{ busy === "preview" ? "Đang tạo…" : "Tạo ảnh thử" }}
      </button>
    </section>
  </div>
</template>

<style scoped>
.steps {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  list-style: none;
  margin: 0;
  padding: 0;
}
.steps li {
  align-items: center;
  background: var(--white);
  border: 1.5px solid var(--line);
  border-radius: 20px;
  display: flex;
  gap: 12px;
  padding: 14px 16px;
}
.steps li.done {
  background: var(--green-bg);
  border-color: transparent;
}
.steps li.current {
  background: var(--cobalt);
  border-color: var(--cobalt);
  color: var(--white);
}
.step-num {
  align-items: center;
  background: var(--soft);
  border-radius: 50%;
  display: flex;
  flex: none;
  font-weight: 800;
  height: 34px;
  justify-content: center;
  width: 34px;
}
.done .step-num {
  background: var(--green);
  color: var(--white);
}
.current .step-num {
  background: var(--white);
  color: var(--cobalt);
}
.node-index {
  align-items: center;
  background: var(--ink);
  border-radius: 12px;
  color: var(--white);
  display: flex;
  flex: none;
  font-weight: 700;
  height: 40px;
  justify-content: center;
  width: 40px;
}
.board-thumb {
  background: repeating-conic-gradient(var(--ink) 0 25%, #fff 0 50%) 0 0 / 22px 22px;
  border: 1.5px solid var(--line);
  border-radius: 12px;
  height: 110px;
  width: 160px;
}
.shot-grid {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(auto-fill, minmax(64px, 1fr));
}
.shot {
  aspect-ratio: 4 / 3;
  border: 1.5px dashed #9aa3b2;
  border-radius: 10px;
}
.shot.taken {
  background: repeating-conic-gradient(var(--ink) 0 25%, var(--bg) 0 50%) 0 0 / 12px 12px;
  border-style: solid;
}
.result-box {
  align-items: center;
  background: #2b2530;
  border-radius: 18px;
  color: #c7ccd6;
  display: flex;
  font-size: 12px;
  height: 160px;
  justify-content: center;
  overflow: hidden;
  width: 240px;
}
.result-box img {
  height: 100%;
  object-fit: cover;
  width: 100%;
}
</style>
