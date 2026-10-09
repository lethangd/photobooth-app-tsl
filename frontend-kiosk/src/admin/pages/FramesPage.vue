<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { KIOSK, getJson, request, type FrameInfo } from "../api";
import AIcon from "../components/AIcon.vue";
import { bytes } from "../format";
import { errorText, notify } from "../state";

const SLOT_OPTIONS = [2, 3, 4];

const frames = ref<FrameInfo[]>([]);
const filter = ref(0);
const slotCount = ref(3);
const dragging = ref(false);
const uploading = ref(false);
const uploadError = ref<{ file: string; text: string } | null>(null);
const preview = ref<FrameInfo | null>(null);
const confirmDelete = ref<FrameInfo | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const nonce = ref(Date.now());

const groups = computed(() =>
  SLOT_OPTIONS.filter((slots) => !filter.value || filter.value === slots)
    .map((slots) => ({ slots, items: frames.value.filter((frame) => frame.slot_count === slots) }))
    .filter((group) => !filter.value || group.items.length || group.slots === filter.value),
);

function previewUrl(frame: FrameInfo): string {
  return `${frame.preview_url}?v=${nonce.value}`;
}

/** Detected slots as % boxes over the preview, the same way the kiosk will place the photos. */
function slotStyle(frame: FrameInfo, slot: FrameInfo["slots"][number]): Record<string, string> {
  return {
    left: `${(slot.x / frame.width) * 100}%`,
    top: `${(slot.y / frame.height) * 100}%`,
    width: `${(slot.width / frame.width) * 100}%`,
    height: `${(slot.height / frame.height) * 100}%`,
  };
}

async function load(): Promise<void> {
  try {
    frames.value = await getJson<FrameInfo[]>(`${KIOSK}/frames`);
    nonce.value = Date.now();
  } catch (exc) {
    notify(errorText(exc), true);
  }
}

async function upload(file: File | undefined): Promise<void> {
  if (!file || uploading.value) return;
  uploading.value = true;
  uploadError.value = null;
  const form = new FormData();
  form.append("file", file);
  form.append("slot_count", String(slotCount.value));
  try {
    await request(`${KIOSK}/frames`, { method: "POST", body: form });
    notify(`Đã thêm khung "${file.name}" (${slotCount.value} ô)`);
    await load();
  } catch (exc) {
    uploadError.value = { file: file.name, text: errorText(exc) };
  } finally {
    uploading.value = false;
    if (fileInput.value) fileInput.value.value = "";
  }
}

function onDrop(event: DragEvent): void {
  dragging.value = false;
  void upload(event.dataTransfer?.files?.[0]);
}

async function remove(frame: FrameInfo): Promise<void> {
  confirmDelete.value = null;
  try {
    await request(`${KIOSK}/frames/${encodeURIComponent(frame.id)}`, { method: "DELETE" });
    notify(`Đã xoá khung "${frame.file_name}" (chuyển vào thùng rác)`);
    await load();
  } catch (exc) {
    notify(errorText(exc), true);
  }
}

onMounted(() => void load());
</script>

<template>
  <div style="display: flex; flex-direction: column; gap: 22px">
    <header class="page-head">
      <div>
        <div class="kicker">{{ frames.length }} khung đang dùng</div>
        <h1 class="h1">Khung ảnh</h1>
      </div>
      <div class="seg" role="group" aria-label="Lọc theo số ảnh">
        <button type="button" :class="{ on: filter === 0 }" @click="filter = 0">Tất cả</button>
        <button
          v-for="slots in SLOT_OPTIONS"
          :key="slots"
          type="button"
          :class="{ on: filter === slots }"
          @click="filter = slots"
        >
          {{ slots }} ảnh
        </button>
      </div>
    </header>

    <section class="card upload" aria-label="Thêm khung mới">
      <div class="upload-text">
        <h2 class="h2" style="font-size: 20px">Thêm khung mới</h2>
        <p class="muted" style="margin: 0; font-size: 15px; line-height: 1.55">
          Thiết kế khung bằng Canva hoặc Photoshop, để các ô ảnh là
          <strong style="color: var(--ink)">hình chữ nhật trắng hoặc đen đặc</strong>. Máy sẽ tự tìm vị trí
          từng ô.
        </p>
        <div>
          <div class="kicker" style="font-size: 11px; margin-bottom: 8px">1 · Khung có mấy ảnh?</div>
          <div role="radiogroup" aria-label="Số ô ảnh" style="display: flex; gap: 10px">
            <button
              v-for="slots in SLOT_OPTIONS"
              :key="slots"
              type="button"
              role="radio"
              class="slot-btn"
              :class="{ on: slotCount === slots }"
              :aria-checked="slotCount === slots"
              @click="slotCount = slots"
            >
              {{ slots }}
            </button>
          </div>
        </div>
      </div>
      <label
        class="drop"
        :class="{ over: dragging, busy: uploading }"
        @dragover.prevent="dragging = true"
        @dragleave="dragging = false"
        @drop.prevent="onDrop"
      >
        <span class="round-icon" style="background: var(--cobalt); color: #fff; width: 64px; height: 64px"
          ><AIcon name="upload" :size="28" :stroke="2.4"
        /></span>
        <span style="font-weight: 800; font-size: 18px">{{
          uploading ? "Đang kiểm tra khung…" : "2 · Kéo thả file khung vào đây"
        }}</span>
        <span class="muted" style="font-size: 14px">hoặc bấm để chọn · PNG, JPG, WebP · tối đa 30 MB</span>
        <input
          ref="fileInput"
          type="file"
          accept="image/png,image/jpeg,image/webp"
          class="sr-only"
          @change="upload(($event.target as HTMLInputElement).files?.[0])"
        />
      </label>
    </section>

    <div v-if="uploadError" class="alert error" role="alert">
      <span class="alert-icon">!</span>
      <span class="alert-body">
        <strong>"{{ uploadError.file }}" chưa được thêm</strong>
        <span>{{ uploadError.text }}</span>
      </span>
      <button type="button" class="btn btn-ghost btn-sm" @click="uploadError = null">Đóng</button>
    </div>

    <section
      v-for="group in groups"
      :key="group.slots"
      style="display: flex; flex-direction: column; gap: 12px"
    >
      <div style="display: flex; align-items: baseline; gap: 10px">
        <h2 style="margin: 0; font-family: var(--display); font-weight: 800; font-size: 20px">
          Khung {{ group.slots }} ảnh
        </h2>
        <span class="muted" style="font-size: 14px">{{ group.items.length }} khung</span>
      </div>
      <div v-if="!group.items.length" class="empty">
        Chưa có khung {{ group.slots }} ảnh. Gói này sẽ không hiện trên kiosk.
      </div>
      <div class="frame-grid">
        <article v-for="frame in group.items" :key="frame.id" class="frame-card">
          <button
            type="button"
            class="frame-stage"
            :aria-label="`Xem trước ${frame.file_name}`"
            @click="preview = frame"
          >
            <span class="frame-box" :style="{ aspectRatio: `${frame.width} / ${frame.height}` }">
              <img :src="previewUrl(frame)" :alt="frame.name" loading="lazy" />
              <i
                v-for="(slot, index) in frame.slots"
                :key="index"
                class="slot"
                :style="slotStyle(frame, slot)"
              />
            </span>
          </button>
          <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px">
            <div style="min-width: 0">
              <div class="ellipsis" style="font-weight: 800">
                {{ frame.file_name.replace(/\.[^.]+$/, "") }}
              </div>
              <div class="mono muted" style="font-size: 11px">
                {{ frame.width }}×{{ frame.height }} · {{ bytes(frame.file_size) }}
              </div>
            </div>
            <span class="pill ok">Nhận {{ frame.slots.length }} ô</span>
          </div>
          <div style="display: flex; gap: 8px">
            <button type="button" class="btn btn-ghost btn-sm" style="flex: 1" @click="preview = frame">
              Xem trước
            </button>
            <button
              type="button"
              class="btn btn-danger btn-sm"
              style="width: 40px; padding: 0"
              aria-label="Xoá khung"
              @click="confirmDelete = frame"
            >
              <AIcon name="trash" :size="18" />
            </button>
          </div>
        </article>
      </div>
    </section>

    <div v-if="preview" class="modal-back" @click.self="preview = null">
      <div class="modal" style="max-width: 560px; align-items: center">
        <div style="width: 100%; display: flex; justify-content: space-between; align-items: center">
          <strong>{{ preview.file_name }}</strong>
          <button type="button" class="btn btn-ghost btn-sm" @click="preview = null">Đóng</button>
        </div>
        <span
          class="frame-box"
          :style="{ aspectRatio: `${preview.width} / ${preview.height}`, maxHeight: '70vh' }"
        >
          <img :src="previewUrl(preview)" :alt="preview.name" />
          <i
            v-for="(slot, index) in preview.slots"
            :key="index"
            class="slot"
            :style="slotStyle(preview, slot)"
            >{{ index + 1 }}</i
          >
        </span>
        <p class="muted" style="margin: 0; font-size: 14px">
          Khung viền xanh nét đứt là ô ảnh máy đã nhận diện, số là thứ tự ảnh khách chọn.
        </p>
      </div>
    </div>

    <div v-if="confirmDelete" class="modal-back" @click.self="confirmDelete = null">
      <div class="modal" role="alertdialog" aria-label="Xoá khung">
        <h2 class="h2" style="font-size: 22px">Xoá khung này?</h2>
        <p class="muted" style="margin: 0">
          "{{ confirmDelete.file_name }}" sẽ được chuyển vào thùng rác và không hiện trên kiosk nữa.
        </p>
        <div class="actions" style="justify-content: flex-end">
          <button type="button" class="btn btn-ghost" @click="confirmDelete = null">Huỷ</button>
          <button type="button" class="btn btn-danger" @click="remove(confirmDelete)">Xoá khung</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.upload {
  flex-direction: row;
  flex-wrap: wrap;
  gap: 18px;
  border-radius: 28px;
}
.upload-text {
  display: flex;
  flex: 1 1 280px;
  flex-direction: column;
  gap: 14px;
}
.slot-btn {
  background: var(--white);
  border: 1.5px solid var(--line);
  border-radius: 18px;
  flex: 1;
  font-family: var(--display);
  font-size: 18px;
  font-weight: 800;
  height: 56px;
  transition: transform 0.25s var(--spring);
}
.slot-btn.on {
  background: var(--cobalt);
  border-color: var(--cobalt);
  box-shadow: 0 10px 22px rgba(43, 59, 255, 0.3);
  color: var(--white);
}
.slot-btn:active {
  transform: scale(0.95);
}
.drop {
  align-items: center;
  background: var(--cobalt-soft);
  border: 2.5px dashed var(--cobalt);
  border-radius: 22px;
  cursor: pointer;
  display: flex;
  flex: 2 1 360px;
  flex-direction: column;
  gap: 10px;
  justify-content: center;
  min-height: 200px;
  padding: 20px;
  text-align: center;
  transition:
    background 0.2s,
    transform 0.25s var(--spring);
}
.drop.over {
  background: #dfe3ff;
  transform: scale(1.01);
}
.drop.busy {
  opacity: 0.7;
  pointer-events: none;
}
.frame-grid {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
}
.frame-card {
  background: var(--white);
  border: 1.5px solid var(--line);
  border-radius: 22px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
}
.frame-stage {
  align-items: center;
  background: #f1f3f7;
  border: 0;
  border-radius: 14px;
  display: flex;
  height: 220px;
  justify-content: center;
  padding: 12px;
}
.frame-box {
  box-shadow: 0 10px 24px rgba(20, 22, 28, 0.18);
  display: block;
  max-height: 100%;
  max-width: 100%;
  position: relative;
}
.frame-stage .frame-box {
  height: 100%;
}
.frame-box img {
  display: block;
  height: 100%;
  object-fit: contain;
  width: 100%;
}
.slot {
  align-items: center;
  border: 2px dashed var(--cobalt);
  border-radius: 3px;
  color: var(--cobalt);
  display: flex;
  font-family: var(--display);
  font-style: normal;
  font-weight: 800;
  justify-content: center;
  position: absolute;
}
.ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
