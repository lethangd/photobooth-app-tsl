<script setup lang="ts">
/** 03f · Discount code typed on an on-screen keyboard; checked against the server while typing. */
import { ref, watch } from "vue";

import { checkVoucher } from "@/api/framebooth";
import type { VoucherCheck } from "@/api/types";
import * as sfx from "@/lib/sfx";

import Icon from "./Icon.vue";
import Star from "./Star.vue";

const props = defineProps<{ open: boolean; slotCount: number }>();
const emit = defineEmits<{ close: []; apply: [result: VoucherCheck] }>();

const ROWS = ["1234567890", "QWERTYUIOP", "ASDFGHJKL-", "ZXCVBNM"];
const MAX_LENGTH = 20;

const code = ref("");
const result = ref<VoucherCheck | null>(null);
const checking = ref(false);
let checkTimer = 0;
let checkRun = 0;

function money(value: number): string {
  return `${new Intl.NumberFormat("vi-VN").format(value)}đ`;
}

watch(
  () => props.open,
  (open) => {
    if (!open) return;
    code.value = "";
    result.value = null;
  },
);

watch(code, (value) => {
  window.clearTimeout(checkTimer);
  result.value = null;
  if (value.length < 3) return;
  checkTimer = window.setTimeout(() => void check(value), 350);
});

async function check(value: string): Promise<void> {
  const run = (checkRun += 1);
  checking.value = true;
  try {
    const checked = await checkVoucher(value, props.slotCount);
    if (run === checkRun) result.value = checked;
  } catch {
    if (run === checkRun) result.value = { ok: false, message: "Chưa kiểm tra được mã, thử lại nhé" };
  } finally {
    if (run === checkRun) checking.value = false;
  }
}

function press(key: string): void {
  sfx.pop();
  if (key === "back") code.value = code.value.slice(0, -1);
  else if (code.value.length < MAX_LENGTH) code.value += key;
}

function apply(): void {
  if (!result.value?.ok) return;
  sfx.chime();
  emit("apply", result.value);
}
</script>

<template>
  <Transition name="dialog">
    <div v-if="open" class="dialog-backdrop" @pointerdown.self="emit('close')">
      <div class="dialog chrome-ring voucher" role="dialog" aria-label="Nhập mã giảm giá">
        <div class="dialog-inner voucher-inner">
          <div class="voucher-head">
            <span class="voucher-badge"><Icon name="tag" :size="30" /></span>
            <div>
              <div class="mono muted">Ưu đãi</div>
              <div class="display voucher-title">Nhập mã giảm giá</div>
            </div>
          </div>

          <div class="voucher-field" :class="{ bad: result && !result.ok, good: result?.ok }">
            <span class="display voucher-code">{{ code || "" }}</span>
            <span class="caret" />
            <span v-if="!code" class="voucher-placeholder">VD: TSL-HELLO</span>
          </div>

          <div class="voucher-status" aria-live="polite">
            <template v-if="result?.ok">
              <Icon name="check" :size="22" :stroke="3" />
              Áp dụng được: {{ result.label?.toLowerCase() }} · còn
              <span class="display">{{ money(result.total ?? 0) }}</span>
            </template>
            <template v-else-if="result">
              <Icon name="alert" :size="22" :stroke="3" />
              {{ result.message }}
            </template>
            <template v-else-if="checking">Đang kiểm tra…</template>
            <template v-else>&nbsp;</template>
          </div>

          <div class="keyboard">
            <div v-for="row in ROWS" :key="row" class="kb-row">
              <button
                v-for="key in row.split('')"
                :key="key"
                class="kb-key display"
                type="button"
                @click="press(key)"
              >
                {{ key === "-" ? "−" : key }}
              </button>
              <button
                v-if="row === 'ZXCVBNM'"
                class="kb-key kb-key--wide"
                type="button"
                aria-label="Xoá"
                @click="press('back')"
              >
                <Icon name="backspace" :size="24" :stroke="2" />
              </button>
            </div>
          </div>

          <div class="row-actions">
            <button class="btn btn-ghost btn-md" type="button" @click="emit('close')">Huỷ</button>
            <button
              class="btn btn-primary btn-md btn-arrowed"
              type="button"
              :disabled="!result?.ok"
              @click="apply"
            >
              Áp dụng mã
              <span class="btn-arrow"><Icon name="arrow-right" :size="20" :stroke="2.6" /></span>
            </button>
          </div>
        </div>
        <Star class="dialog-star" />
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.voucher {
  width: 82rem;
}
.voucher-inner {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  padding: 4.4rem 5rem;
}
.voucher-head {
  align-items: center;
  display: flex;
  gap: 1.8rem;
}
.voucher-badge {
  align-items: center;
  background: var(--cobalt);
  border-radius: 50%;
  box-shadow: 0 0 0 1.2rem #eef0ff;
  color: var(--white);
  display: flex;
  flex: none;
  height: 6.4rem;
  justify-content: center;
  width: 6.4rem;
}
.voucher-title {
  font-size: 3.2rem;
  line-height: 1.15;
  margin-top: 0.4rem;
}
.voucher-field {
  align-items: center;
  background: #f1f3f7;
  border: 2px solid var(--cobalt);
  border-radius: 4rem;
  display: flex;
  gap: 1.4rem;
  height: 8rem;
  padding: 0 2.8rem;
  position: relative;
}
.voucher-field.bad {
  border-color: var(--red);
}
.voucher-field.good {
  border-color: #0f7a66;
}
.voucher-code {
  font-size: 3.2rem;
  letter-spacing: 0.08em;
}
.voucher-placeholder {
  color: #9aa0ae;
  font-size: 2.2rem;
  font-weight: 700;
  left: 4.4rem;
  position: absolute;
}
.caret {
  animation: blink 1s steps(2, start) infinite;
  background: var(--cobalt);
  height: 3.8rem;
  width: 3px;
}
.voucher-status {
  align-items: center;
  color: #0f7a66;
  display: flex;
  font-size: 1.8rem;
  font-weight: 700;
  gap: 1rem;
  min-height: 2.6rem;
}
.voucher-field.bad + .voucher-status {
  color: var(--red);
}
.voucher-status .display {
  font-size: 2rem;
}
.keyboard {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}
.kb-row {
  display: flex;
  gap: 0.8rem;
  justify-content: center;
}
.kb-key {
  align-items: center;
  background: var(--white);
  border: 1.5px solid var(--line);
  border-radius: 1.8rem;
  display: flex;
  font-size: 2rem;
  font-weight: 600;
  height: 6rem;
  justify-content: center;
  transition: scale 420ms var(--spring);
  width: 6rem;
}
.kb-key:active {
  background: #eef0ff;
  scale: 0.9;
  transition-duration: 80ms;
}
.kb-key--wide {
  background: #eef0f5;
  width: 9rem;
}
@keyframes blink {
  to {
    visibility: hidden;
  }
}
@media (orientation: portrait) {
  .voucher {
    width: 84rem;
  }
}
</style>
