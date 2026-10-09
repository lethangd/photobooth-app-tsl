<script setup lang="ts">
/**
 * 06b · Decorate the collage: stickers, text and freehand drawing laid over the preview.
 * Positions are kept relative to the collage (0..1) so `exportOverlay()` can redraw everything at the
 * print resolution as a transparent PNG that the server lays over the final collage.
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

import {
  PEN_COLORS,
  STICKER_PACKS,
  TEXT_STYLES,
  chipBackground,
  isHolo,
  svgUrl,
  type StickerDef,
} from "@/lib/stickers";
import * as sfx from "@/lib/sfx";
import { typeTelex } from "@/lib/telex";

import Icon from "./Icon.vue";
import Star from "./Star.vue";

const props = defineProps<{ previewUrl: string; width: number; height: number; defaultText: string }>();
const emit = defineEmits<{ skip: []; done: [] }>();

type Tab = "sticker" | "text" | "draw";
interface Item {
  id: number;
  x: number;
  y: number;
  size: number; // fraction of the collage width (svg: side length, text: font size)
  rot: number;
  svg?: string;
  text?: string;
  bg?: string;
  ink?: string;
}
interface Stroke {
  color: string;
  width: number; // fraction of the collage width
  points: [number, number][];
}

const KEY_ROWS = ["qwertyuiop", "asdfghjkl", "zxcvbnm"];
const PEN_SIZES = [0.008, 0.016, 0.03];
const MAX_TEXT = 28;

const tab = ref<Tab>("sticker");
const packId = ref(STICKER_PACKS[0].id);
const items = ref<Item[]>([]);
const strokes = ref<Stroke[]>([]);
const selectedId = ref<number | null>(null);
const history: string[] = [];
const historySize = ref(0);
const text = ref(props.defaultText);
const textStyle = ref(TEXT_STYLES[0].id);
const penColor = ref(PEN_COLORS[0]);
const penSize = ref(PEN_SIZES[1]);
const box = ref<HTMLElement | null>(null);
const canvas = ref<HTMLCanvasElement | null>(null);
let nextId = 1;
let resizeObserver: ResizeObserver | null = null;

const pack = computed(() => STICKER_PACKS.find((p) => p.id === packId.value) ?? STICKER_PACKS[0]);
const selected = computed(() => items.value.find((item) => item.id === selectedId.value) ?? null);
const hasContent = computed(() => items.value.length > 0 || strokes.value.length > 0);
const presets = computed(() => {
  const day = new Date();
  const date = `${String(day.getDate()).padStart(2, "0")}.${String(day.getMonth() + 1).padStart(2, "0")}`;
  return [
    props.defaultText,
    `Hội bạn thân · ${date}`,
    "Kỷ niệm đẹp",
    "Besties forever",
    `TSL · ${day.getFullYear()}`,
  ].filter((value, index, all) => value && all.indexOf(value) === index);
});
const boxStyle = computed(() => ({
  aspectRatio: `${props.width} / ${props.height}`,
  "--ar": String(props.width / Math.max(1, props.height)),
}));

// ───── history ─────

function snapshot(): void {
  history.push(JSON.stringify({ items: items.value, strokes: strokes.value }));
  if (history.length > 40) history.shift();
  historySize.value = history.length;
}

function undo(): void {
  const last = history.pop();
  historySize.value = history.length;
  if (!last) return;
  sfx.pop();
  const state = JSON.parse(last) as { items: Item[]; strokes: Stroke[] };
  items.value = state.items;
  strokes.value = state.strokes;
  selectedId.value = null;
  redraw();
}

function removeSelected(): void {
  if (!selected.value) return;
  snapshot();
  sfx.pop();
  items.value = items.value.filter((item) => item.id !== selectedId.value);
  selectedId.value = null;
}

// ───── adding ─────

function addItem(item: Omit<Item, "id" | "x" | "y" | "rot">): void {
  snapshot();
  sfx.pop();
  const offset = (items.value.length % 5) * 0.04;
  const added: Item = {
    id: nextId++,
    x: 0.5 + offset - 0.08,
    y: 0.42 + offset,
    rot: -6 + Math.random() * 12,
    ...item,
  };
  items.value = [...items.value, added];
  selectedId.value = added.id;
}

function addSticker(def: StickerDef): void {
  if (def.kind === "svg") addItem({ svg: def.svg, size: 0.26 });
  else addItem({ text: def.text, bg: def.bg, ink: def.ink, size: 0.075 });
}

function addText(): void {
  const value = text.value.trim();
  if (!value) return;
  const style = TEXT_STYLES.find((s) => s.id === textStyle.value) ?? TEXT_STYLES[0];
  addItem({ text: value, bg: style.bg, ink: style.ink, size: 0.06 });
}

function pressKey(key: string): void {
  sfx.pop();
  if (key === "back") text.value = text.value.slice(0, -1);
  else if (key === "space") text.value = text.value.length < MAX_TEXT ? `${text.value} ` : text.value;
  else if (key === "clear") text.value = "";
  else if (text.value.length < MAX_TEXT) {
    const startOfText = text.value.length === 0;
    text.value = typeTelex(text.value, startOfText ? key.toUpperCase() : key);
  }
}

// ───── moving / resizing ─────

let gesture:
  | { kind: "move"; id: number; startX: number; startY: number; itemX: number; itemY: number; moved: boolean }
  | {
      kind: "scale";
      id: number;
      cx: number;
      cy: number;
      dist: number;
      angle: number;
      size: number;
      rot: number;
    }
  | null = null;

function boxRect(): DOMRect | null {
  return box.value?.getBoundingClientRect() ?? null;
}

function onItemDown(event: PointerEvent, item: Item): void {
  if (tab.value === "draw") return;
  event.stopPropagation();
  selectedId.value = item.id;
  (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  gesture = {
    kind: "move",
    id: item.id,
    startX: event.clientX,
    startY: event.clientY,
    itemX: item.x,
    itemY: item.y,
    moved: false,
  };
}

function onHandleDown(event: PointerEvent, item: Item): void {
  event.stopPropagation();
  const rect = boxRect();
  if (!rect) return;
  (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  const cx = rect.left + item.x * rect.width;
  const cy = rect.top + item.y * rect.height;
  gesture = {
    kind: "scale",
    id: item.id,
    cx,
    cy,
    dist: Math.hypot(event.clientX - cx, event.clientY - cy) || 1,
    angle: Math.atan2(event.clientY - cy, event.clientX - cx),
    size: item.size,
    rot: item.rot,
  };
  snapshot();
}

function onGestureMove(event: PointerEvent): void {
  if (!gesture) return;
  const rect = boxRect();
  const item = items.value.find((i) => i.id === gesture?.id);
  if (!rect || !item) return;
  if (gesture.kind === "move") {
    const dx = (event.clientX - gesture.startX) / rect.width;
    const dy = (event.clientY - gesture.startY) / rect.height;
    if (!gesture.moved && Math.hypot(dx, dy) > 0.005) {
      gesture.moved = true;
      snapshot();
    }
    item.x = Math.min(1, Math.max(0, gesture.itemX + dx));
    item.y = Math.min(1, Math.max(0, gesture.itemY + dy));
  } else {
    const dist = Math.hypot(event.clientX - gesture.cx, event.clientY - gesture.cy);
    const angle = Math.atan2(event.clientY - gesture.cy, event.clientX - gesture.cx);
    const limit = item.svg ? [0.08, 0.9] : [0.025, 0.2];
    item.size = Math.min(limit[1], Math.max(limit[0], (gesture.size * dist) / gesture.dist));
    item.rot = gesture.rot + ((angle - gesture.angle) * 180) / Math.PI;
  }
}

function onGestureEnd(): void {
  gesture = null;
}

function onBoxDown(event: PointerEvent): void {
  if (tab.value === "draw") return startStroke(event);
  selectedId.value = null;
}

// ───── drawing ─────

let drawing: Stroke | null = null;

function pointIn(event: PointerEvent): [number, number] | null {
  const rect = boxRect();
  if (!rect) return null;
  return [(event.clientX - rect.left) / rect.width, (event.clientY - rect.top) / rect.height];
}

function startStroke(event: PointerEvent): void {
  const point = pointIn(event);
  if (!point) return;
  (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  snapshot();
  drawing = { color: penColor.value, width: penSize.value, points: [point] };
  strokes.value = [...strokes.value, drawing];
}

function onBoxMove(event: PointerEvent): void {
  if (gesture) return onGestureMove(event);
  if (!drawing) return;
  const point = pointIn(event);
  if (!point) return;
  drawing.points.push(point);
  redraw();
}

function onBoxUp(): void {
  gesture = null;
  drawing = null;
}

function clearDrawing(): void {
  if (!strokes.value.length) return;
  snapshot();
  strokes.value = [];
  redraw();
}

function paintStrokes(ctx: CanvasRenderingContext2D, w: number, h: number, list: Stroke[]): void {
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  for (const stroke of list) {
    ctx.strokeStyle = stroke.color;
    ctx.lineWidth = stroke.width * w;
    ctx.beginPath();
    stroke.points.forEach(([x, y], i) => (i ? ctx.lineTo(x * w, y * h) : ctx.moveTo(x * w, y * h)));
    if (stroke.points.length === 1) ctx.lineTo(stroke.points[0][0] * w + 0.1, stroke.points[0][1] * h);
    ctx.stroke();
  }
}

function redraw(): void {
  const el = canvas.value;
  const rect = boxRect();
  if (!el || !rect) return;
  const dpr = window.devicePixelRatio || 1;
  if (el.width !== Math.round(rect.width * dpr)) {
    el.width = Math.round(rect.width * dpr);
    el.height = Math.round(rect.height * dpr);
  }
  const ctx = el.getContext("2d");
  if (!ctx) return;
  ctx.clearRect(0, 0, el.width, el.height);
  paintStrokes(ctx, el.width, el.height, strokes.value);
}

watch(strokes, () => redraw(), { deep: false });

// ───── export at print size ─────

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

function chipFill(
  ctx: CanvasRenderingContext2D,
  bg: string,
  x: number,
  width: number,
): string | CanvasGradient {
  if (!isHolo(bg)) return bg;
  const gradient = ctx.createLinearGradient(x, 0, x + width, 0);
  gradient.addColorStop(0, "#C9B8FF");
  gradient.addColorStop(0.5, "#A8F0E0");
  gradient.addColorStop(1, "#FFD2B8");
  return gradient;
}

/** Transparent PNG (data URL) of everything added, at the collage resolution; null when nothing was added. */
async function exportOverlay(): Promise<string | null> {
  if (!hasContent.value) return null;
  await document.fonts.ready;
  const w = props.width;
  const h = props.height;
  const out = document.createElement("canvas");
  out.width = w;
  out.height = h;
  const ctx = out.getContext("2d");
  if (!ctx) return null;
  paintStrokes(ctx, w, h, strokes.value);
  for (const item of items.value) {
    ctx.save();
    ctx.translate(item.x * w, item.y * h);
    ctx.rotate((item.rot * Math.PI) / 180);
    if (item.svg) {
      const side = item.size * w;
      const img = await loadImage(svgUrl(item.svg));
      ctx.drawImage(img, -side / 2, -side / 2, side, side);
    } else if (item.text) {
      const size = item.size * w;
      ctx.font = `800 ${size}px Unbounded, "Be Vietnam Pro", sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      const tw = ctx.measureText(item.text).width;
      const pw = tw + size * 1.4;
      const ph = size * 1.9;
      if (item.bg && item.bg !== "transparent") {
        ctx.fillStyle = chipFill(ctx, item.bg, -pw / 2, pw);
        ctx.beginPath();
        ctx.roundRect(-pw / 2, -ph / 2, pw, ph, ph / 2);
        ctx.fill();
      } else {
        ctx.shadowColor = "rgba(0,0,0,.55)";
        ctx.shadowBlur = size * 0.3;
      }
      ctx.fillStyle = item.ink ?? "#14161C";
      ctx.fillText(item.text, 0, size * 0.06);
    }
    ctx.restore();
  }
  return out.toDataURL("image/png");
}

function reset(): void {
  items.value = [];
  strokes.value = [];
  history.length = 0;
  historySize.value = 0;
  selectedId.value = null;
  text.value = props.defaultText;
  redraw();
}

defineExpose({ exportOverlay, hasContent, reset });

onMounted(async () => {
  await nextTick();
  if (box.value) {
    resizeObserver = new ResizeObserver(() => redraw());
    resizeObserver.observe(box.value);
  }
});
onBeforeUnmount(() => resizeObserver?.disconnect());
</script>

<template>
  <div class="deco-screen">
    <section class="deco-stage e-bg" style="--i: 0; --fx: -30rem">
      <div
        ref="box"
        class="deco-box e-card"
        :class="{ drawing: tab === 'draw' }"
        :style="{ ...boxStyle, '--i': 1, '--rot': '0deg' }"
        @pointerdown="onBoxDown"
        @pointermove="onBoxMove"
        @pointerup="onBoxUp"
        @pointercancel="onBoxUp"
      >
        <img class="deco-photo" :src="previewUrl" alt="Ảnh ghép của bạn" draggable="false" />
        <canvas ref="canvas" class="deco-canvas" />
        <div
          v-for="item in items"
          :key="item.id"
          class="deco-item"
          :class="{ selected: item.id === selectedId }"
          :style="{
            left: `${item.x * 100}%`,
            top: `${item.y * 100}%`,
            '--s': item.size,
            transform: `translate(-50%, -50%) rotate(${item.rot}deg)`,
          }"
          @pointerdown="onItemDown($event, item)"
          @pointermove="onGestureMove"
          @pointerup="onGestureEnd"
          @pointercancel="onGestureEnd"
        >
          <img v-if="item.svg" class="deco-svg" :src="svgUrl(item.svg)" alt="" draggable="false" />
          <span
            v-else
            class="deco-chip"
            :class="{ bare: item.bg === 'transparent' }"
            :style="{ background: chipBackground(item.bg ?? '#fff'), color: item.ink }"
            >{{ item.text }}</span
          >
          <button
            v-if="item.id === selectedId"
            class="deco-handle"
            type="button"
            aria-label="Kéo để phóng to, xoay"
            @pointerdown="onHandleDown($event, item)"
            @pointermove="onGestureMove"
            @pointerup="onGestureEnd"
            @pointercancel="onGestureEnd"
          >
            <Icon name="refresh" :size="18" :stroke="2.6" />
          </button>
        </div>
      </div>
      <div class="deco-tools">
        <button class="btn btn-ghost btn-sm" type="button" :disabled="!historySize" @click="undo">
          <Icon name="undo" :size="18" /> Hoàn tác
        </button>
        <button class="btn btn-ghost btn-sm" type="button" :disabled="!selected" @click="removeSelected">
          <Icon name="trash" :size="18" /> Xoá sticker
        </button>
      </div>
    </section>

    <section class="deco-controls">
      <div>
        <div class="mono muted e-pop" style="--i: 1">Bước 05B — Trang trí</div>
        <h1 class="display deco-title">
          <span class="ln"
            ><span class="e-line" style="--i: 2">Trang trí <span class="accent">ảnh</span></span></span
          >
        </h1>
      </div>

      <div class="deco-tabs e-pop" style="--i: 3" role="tablist">
        <button
          v-for="t in [
            { id: 'sticker', label: 'Sticker', icon: 'smile' },
            { id: 'text', label: 'Chữ', icon: 'type' },
            { id: 'draw', label: 'Vẽ tay', icon: 'pen' },
          ] as const"
          :key="t.id"
          class="display"
          :class="{ on: tab === t.id }"
          type="button"
          role="tab"
          :aria-selected="tab === t.id"
          @click="
            tab = t.id;
            selectedId = null;
          "
        >
          <Icon :name="t.icon" :size="20" /> {{ t.label }}
        </button>
      </div>

      <!-- stickers -->
      <template v-if="tab === 'sticker'">
        <div class="chip-row">
          <button
            v-for="p in STICKER_PACKS"
            :key="p.id"
            class="mono pack"
            :class="{ on: p.id === packId }"
            type="button"
            @click="packId = p.id"
          >
            {{ p.name }}
          </button>
        </div>
        <div class="sticker-grid">
          <button
            v-for="def in pack.items"
            :key="def.id"
            class="sticker-tile"
            type="button"
            :aria-label="def.label"
            @click="addSticker(def)"
          >
            <img v-if="def.kind === 'svg'" :src="svgUrl(def.svg)" alt="" />
            <span
              v-else
              class="display tile-chip"
              :style="{ background: chipBackground(def.bg), color: def.ink }"
              >{{ def.text }}</span
            >
          </button>
        </div>
      </template>

      <!-- text -->
      <template v-else-if="tab === 'text'">
        <div class="text-field">
          <span class="mono muted">Chữ trên ảnh</span>
          <span class="text-value">{{ text }}</span
          ><span class="caret" />
        </div>
        <div class="chip-row">
          <button v-for="p in presets" :key="p" class="pack preset" type="button" @click="text = p">
            {{ p }}
          </button>
        </div>
        <div class="text-keys">
          <div v-for="row in KEY_ROWS" :key="row" class="key-row">
            <button v-for="k in row.split('')" :key="k" class="tkey" type="button" @click="pressKey(k)">
              {{ k }}
            </button>
          </div>
          <div class="key-row">
            <button class="tkey tkey--soft" type="button" @click="pressKey('clear')">Xoá hết</button>
            <button class="tkey tkey--space" type="button" @click="pressKey('space')">dấu cách</button>
            <button class="tkey tkey--soft" type="button" aria-label="Xoá" @click="pressKey('back')">
              <Icon name="backspace" :size="22" :stroke="2" />
            </button>
          </div>
          <div class="mono muted telex-hint">Gõ kiểu Telex: aa → â · dd → đ · s f r x j → dấu</div>
        </div>
        <div class="text-actions">
          <div class="swatches">
            <button
              v-for="style in TEXT_STYLES"
              :key="style.id"
              class="swatch"
              :class="{ on: style.id === textStyle, bare: style.bg === 'transparent' }"
              :style="{ background: style.bg === 'transparent' ? '#596071' : chipBackground(style.bg) }"
              type="button"
              :aria-label="style.label"
              @click="textStyle = style.id"
            />
          </div>
          <button class="btn btn-dark btn-md" type="button" :disabled="!text.trim()" @click="addText">
            <Icon name="plus" :size="20" :stroke="2.6" /> Thêm chữ
          </button>
        </div>
      </template>

      <!-- drawing -->
      <template v-else>
        <div class="mono muted">Màu bút</div>
        <div class="swatches">
          <button
            v-for="color in PEN_COLORS"
            :key="color"
            class="swatch swatch--lg"
            :class="{ on: color === penColor }"
            :style="{ background: color }"
            type="button"
            :aria-label="`Màu ${color}`"
            @click="penColor = color"
          />
        </div>
        <div class="mono muted">Nét bút</div>
        <div class="swatches">
          <button
            v-for="(size, index) in PEN_SIZES"
            :key="size"
            class="pen-size"
            :class="{ on: size === penSize }"
            type="button"
            :aria-label="['Nét mảnh', 'Nét vừa', 'Nét đậm'][index]"
            @click="penSize = size"
          >
            <i
              :style="{
                width: `${(index + 1) * 0.8}rem`,
                height: `${(index + 1) * 0.8}rem`,
                background: penColor,
              }"
            />
          </button>
          <button
            class="btn btn-ghost btn-sm"
            type="button"
            :disabled="!strokes.length"
            @click="clearDrawing"
          >
            Xoá nét vẽ
          </button>
        </div>
        <div class="draw-hint">Vẽ trực tiếp lên ảnh bên trái bằng ngón tay.</div>
      </template>

      <div class="row-actions deco-actions">
        <button class="btn btn-ghost btn-md" type="button" @click="emit('skip')">Bỏ qua</button>
        <button class="btn btn-primary btn-md btn-arrowed" type="button" @click="emit('done')">
          Xem kết quả
          <span class="btn-arrow"><Icon name="arrow-right" :size="22" :stroke="2.6" /></span>
        </button>
      </div>
    </section>
    <Star class="e-pop spin-slow deco-star" style="--i: 5" />
  </div>
</template>

<style scoped>
.deco-screen {
  display: flex;
  gap: 5rem;
  height: 100%;
  padding: 2.4rem 5.6rem 2.6rem 4rem;
  position: relative;
}
.deco-stage {
  align-items: center;
  background: var(--lilac);
  border-radius: 23.5rem;
  display: flex;
  flex: none;
  flex-direction: column;
  gap: 2rem;
  justify-content: center;
  padding: 4rem 3rem 3rem;
  width: 50rem;
}
.deco-box {
  background: var(--white);
  border-radius: 1.4rem;
  box-shadow: var(--shadow);
  container-type: inline-size;
  max-height: 62rem;
  max-width: 40rem;
  position: relative;
  touch-action: none;
  width: min(40rem, calc(62rem * var(--ar, 0.5)));
}
.deco-photo {
  border-radius: 1.4rem;
  display: block;
  height: 100%;
  inset: 0;
  object-fit: contain;
  position: absolute;
  width: 100%;
}
.deco-canvas {
  height: 100%;
  inset: 0;
  pointer-events: none;
  position: absolute;
  width: 100%;
}
.deco-item {
  cursor: grab;
  position: absolute;
  touch-action: none;
}
.drawing .deco-item {
  pointer-events: none;
}
.deco-item.selected {
  outline: 2px dashed var(--cobalt);
  outline-offset: 0.6rem;
  border-radius: 1rem;
}
.deco-svg {
  display: block;
  height: calc(var(--s) * 100cqw);
  pointer-events: none;
  width: calc(var(--s) * 100cqw);
}
.deco-chip {
  border-radius: 999px;
  display: block;
  font-family: var(--font-display);
  font-size: calc(var(--s) * 100cqw);
  font-weight: 800;
  line-height: 1;
  padding: 0.45em 0.7em;
  white-space: nowrap;
}
.deco-chip.bare {
  text-shadow: 0 0 0.3em rgba(0, 0, 0, 0.55);
}
.deco-handle {
  align-items: center;
  background: var(--cobalt);
  border: 3px solid var(--white);
  border-radius: 50%;
  bottom: -2.2rem;
  color: var(--white);
  display: flex;
  height: 4.4rem;
  justify-content: center;
  position: absolute;
  right: -2.2rem;
  touch-action: none;
  width: 4.4rem;
}
.deco-tools {
  display: flex;
  gap: 1rem;
}
.btn-sm {
  font-size: 1.3rem;
  gap: 0.8rem;
  height: 4.8rem;
  padding: 0 2rem;
}
.deco-controls {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 1.6rem;
  justify-content: center;
  min-width: 0;
}
.deco-title {
  font-size: 5.2rem;
  line-height: 1.1;
  margin-top: 0.8rem;
}
.deco-tabs {
  background: var(--white);
  border: 1.5px solid var(--line);
  border-radius: 3.2rem;
  display: flex;
  max-width: 56rem;
  padding: 0.5rem;
}
.deco-tabs button {
  align-items: center;
  border-radius: 2.7rem;
  display: flex;
  flex: 1;
  font-size: 1.6rem;
  font-weight: 600;
  gap: 0.8rem;
  height: 5.4rem;
  justify-content: center;
  transition: background 200ms ease;
}
.deco-tabs button.on {
  background: var(--cobalt);
  color: var(--white);
}
.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
}
.pack {
  background: var(--white);
  border: 1.5px solid var(--line);
  border-radius: 2.2rem;
  font-size: 1.2rem;
  height: 4.4rem;
  padding: 0 1.8rem;
}
.pack.on {
  background: var(--ink);
  border-color: var(--ink);
  color: var(--white);
}
.preset {
  font-size: 1.5rem;
  font-weight: 700;
}
.sticker-grid {
  display: grid;
  gap: 1.2rem;
  grid-template-columns: repeat(auto-fill, 10.4rem);
  max-height: 34rem;
  overflow-y: auto;
  padding: 0.4rem;
}
.sticker-tile {
  align-items: center;
  background: var(--white);
  border: 1.5px solid var(--line);
  border-radius: 2.8rem;
  display: flex;
  height: 10.4rem;
  justify-content: center;
  transition: scale 420ms var(--spring);
  width: 10.4rem;
}
.sticker-tile:active {
  border-color: var(--cobalt);
  scale: 0.9;
  transition-duration: 80ms;
}
.sticker-tile img {
  height: 5.6rem;
  width: 5.6rem;
}
.tile-chip {
  border-radius: 999px;
  font-size: 1.5rem;
  max-width: 9rem;
  overflow: hidden;
  padding: 0.7rem 1rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.text-field {
  align-items: center;
  background: var(--white);
  border: 2px solid var(--cobalt);
  border-radius: 3.2rem;
  display: flex;
  gap: 1.2rem;
  height: 6.4rem;
  max-width: 64rem;
  padding: 0 2.4rem;
}
.text-value {
  font-size: 2.2rem;
  font-weight: 800;
  overflow: hidden;
  white-space: nowrap;
}
.caret {
  animation: blink 1s steps(2, start) infinite;
  background: var(--cobalt);
  flex: none;
  height: 3rem;
  width: 3px;
}
.text-keys {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
  max-width: 70rem;
}
.key-row {
  display: flex;
  gap: 0.7rem;
  justify-content: center;
}
.tkey {
  background: var(--white);
  border: 1.5px solid var(--line);
  border-radius: 1.6rem;
  font-family: var(--font-display);
  font-size: 1.9rem;
  font-weight: 600;
  height: 5.6rem;
  transition: scale 420ms var(--spring);
  width: 5.8rem;
}
.tkey:active {
  background: #eef0ff;
  scale: 0.9;
  transition-duration: 80ms;
}
.tkey--soft {
  align-items: center;
  background: #eef0f5;
  display: flex;
  font-size: 1.4rem;
  justify-content: center;
  width: 11rem;
}
.tkey--space {
  font-size: 1.4rem;
  width: 30rem;
}
.telex-hint {
  font-size: 1.1rem;
  text-align: center;
}
.text-actions {
  align-items: center;
  display: flex;
  gap: 2rem;
  justify-content: space-between;
  max-width: 70rem;
}
.swatches {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 1.2rem;
}
.swatch {
  border: 1.5px solid var(--line);
  border-radius: 50%;
  height: 4.4rem;
  width: 4.4rem;
}
.swatch--lg {
  height: 5.6rem;
  width: 5.6rem;
}
.swatch.on {
  outline: 3px solid var(--cobalt);
  outline-offset: 3px;
}
.pen-size {
  align-items: center;
  background: var(--white);
  border: 1.5px solid var(--line);
  border-radius: 50%;
  display: flex;
  height: 5.6rem;
  justify-content: center;
  width: 5.6rem;
}
.pen-size.on {
  outline: 3px solid var(--cobalt);
  outline-offset: 3px;
}
.pen-size i {
  border: 1px solid var(--line);
  border-radius: 50%;
  display: block;
}
.draw-hint {
  color: var(--muted);
  font-size: 1.7rem;
  font-weight: 600;
}
.deco-actions {
  margin-top: 0.6rem;
}
.deco-star {
  position: absolute;
  right: 4rem;
  top: 3rem;
  width: 5.6rem;
}
@keyframes blink {
  to {
    visibility: hidden;
  }
}
@media (orientation: portrait) {
  .deco-screen {
    flex-direction: column;
    gap: 3rem;
    padding: 2.4rem 4rem;
  }
  .deco-stage {
    border-radius: 6rem;
    width: 100%;
  }
}
</style>
