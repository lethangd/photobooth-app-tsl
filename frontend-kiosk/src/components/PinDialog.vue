<script setup lang="ts">
/** Staff PIN pad (03a) and wrong-PIN state (03b). Emits `success` with the point the bubble should grow from. */
import { computed, ref, watch } from "vue";

import { verifyPin } from "@/api/framebooth";
import { sleep } from "@/lib/motion";
import * as sfx from "@/lib/sfx";

import Icon from "./Icon.vue";
import Star from "./Star.vue";

const PIN_LENGTH = 4;

const props = defineProps<{ open: boolean; description: string }>();
const emit = defineEmits<{ close: []; success: [origin: { x: number; y: number }] }>();

const digits = ref("");
const state = ref<"entry" | "checking" | "shake" | "error">("entry");
const lockedSeconds = ref(0);
const confirmButton = ref<HTMLElement | null>(null);

const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "back", "0", "clear"];
const errorText = computed(() =>
  lockedSeconds.value > 0
    ? `Nhập sai quá nhiều lần. Thử lại sau ${lockedSeconds.value} giây.`
    : "Vui lòng kiểm tra và nhập lại, hoặc gọi quản lý để được hỗ trợ.",
);

watch(
  () => props.open,
  (open) => {
    if (open) {
      digits.value = "";
      state.value = "entry";
    }
  },
);

function press(key: string): void {
  if (state.value !== "entry") return;
  sfx.pop();
  if (key === "back") digits.value = digits.value.slice(0, -1);
  else if (key === "clear") digits.value = "";
  else if (digits.value.length < PIN_LENGTH) digits.value += key;
  if (digits.value.length === PIN_LENGTH) void submit();
}

function centerOf(el: Element | null): { x: number; y: number } {
  const rect = el?.getBoundingClientRect();
  return rect
    ? { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 }
    : { x: window.innerWidth / 2, y: window.innerHeight / 2 };
}

async function submit(): Promise<void> {
  if (digits.value.length !== PIN_LENGTH || state.value !== "entry") return;
  state.value = "checking";
  let ok = false;
  try {
    const result = await verifyPin(digits.value);
    ok = result.ok;
    lockedSeconds.value = result.locked_seconds;
  } catch {
    lockedSeconds.value = 0;
  }
  if (ok) {
    emit("success", centerOf(confirmButton.value));
    return;
  }
  sfx.error();
  state.value = "shake";
  await sleep(420);
  state.value = "error";
}

function retry(): void {
  digits.value = "";
  state.value = "entry";
}
</script>

<template>
  <Transition name="dialog">
    <div v-if="open" class="dialog-backdrop" @pointerdown.self="emit('close')">
      <Transition name="dialog-swap" mode="out-in">
        <div
          v-if="state !== 'error'"
          key="entry"
          class="dialog chrome-ring"
          role="dialog"
          aria-label="Nhập mã PIN"
        >
          <div class="dialog-inner pin">
            <div class="pin-side">
              <div class="pin-lock"><Icon name="lock" :size="34" /></div>
              <div>
                <div class="mono muted">Dành cho nhân viên</div>
                <div class="display pin-title">Nhập mã PIN</div>
                <div class="pin-desc">{{ description }}</div>
              </div>
              <div class="pin-slots" :class="{ shake: state === 'shake' }">
                <span
                  v-for="i in PIN_LENGTH"
                  :key="`${i}-${digits.length >= i}`"
                  class="pin-slot"
                  :class="{
                    filled: digits.length >= i,
                    current: digits.length === i - 1,
                    wrong: state === 'shake',
                  }"
                >
                  <i v-if="digits.length >= i" />
                </span>
              </div>
              <div class="row-actions">
                <button class="btn btn-ghost btn-md" type="button" @click="emit('close')">Huỷ</button>
                <button
                  ref="confirmButton"
                  class="btn btn-primary btn-md btn-arrowed"
                  type="button"
                  :disabled="digits.length !== PIN_LENGTH || state !== 'entry'"
                  @click="submit"
                >
                  Xác nhận
                  <span class="btn-arrow"><Icon name="arrow-right" :size="20" :stroke="2.6" /></span>
                </button>
              </div>
            </div>
            <div class="keypad">
              <button
                v-for="key in KEYS"
                :key="key"
                class="key"
                :class="{ 'key--soft': key === 'back' || key === 'clear' }"
                type="button"
                :aria-label="key === 'back' ? 'Xoá' : key === 'clear' ? 'Xoá hết' : key"
                @click="press(key)"
              >
                <Icon v-if="key === 'back'" name="backspace" :size="28" :stroke="2" />
                <Icon v-else-if="key === 'clear'" name="x" :size="26" />
                <span v-else>{{ key }}</span>
              </button>
            </div>
          </div>
          <Star class="dialog-star" />
        </div>

        <div
          v-else
          key="error"
          class="dialog dialog--narrow chrome-ring"
          role="alertdialog"
          aria-label="Mã PIN sai"
        >
          <div class="dialog-inner dialog-center">
            <div class="error-badge"><Icon name="alert" :size="44" :stroke="3" /></div>
            <div>
              <div class="display pin-title">Mã PIN không đúng</div>
              <div class="pin-desc">{{ errorText }}</div>
            </div>
            <div class="pin-slots">
              <span v-for="i in PIN_LENGTH" :key="i" class="pin-slot wrong filled"><i /></span>
            </div>
            <div class="row-actions">
              <button class="btn btn-ghost btn-md" type="button" @click="emit('close')">Huỷ</button>
              <button class="btn btn-primary btn-md btn-arrowed" type="button" @click="retry">
                Nhập lại
                <span class="btn-arrow"><Icon name="arrow-right" :size="20" :stroke="2.6" /></span>
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </div>
  </Transition>
</template>
