<script setup lang="ts">
/** 08b · Loyalty card: the guest types a phone number, gets a stamp, and a free-session code when the card is full. */
import { computed, ref, watch } from "vue";

import { addLoyaltyStamp } from "@/api/framebooth";
import type { LoyaltyResult } from "@/api/types";
import * as sfx from "@/lib/sfx";

import Icon from "./Icon.vue";
import Star from "./Star.vue";

const props = defineProps<{ open: boolean; sessionId: string; target: number }>();
const emit = defineEmits<{ close: []; done: [] }>();

const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "back", "0", "clear"];

const phone = ref("");
const busy = ref(false);
const error = ref("");
const result = ref<LoyaltyResult | null>(null);

const display = computed(() => {
  const digits = phone.value;
  return [digits.slice(0, 4), digits.slice(4, 7), digits.slice(7, 10)].filter(Boolean).join(" ");
});
const valid = computed(() => /^0[35789]\d{8}$/.test(phone.value));
const stampsShown = computed(() => {
  const r = result.value;
  if (!r) return 0;
  return r.reward_code ? r.target : r.stamps;
});
const remaining = computed(() => Math.max(0, (result.value?.target ?? props.target) - stampsShown.value));

watch(
  () => props.open,
  (open) => {
    if (!open) return;
    phone.value = "";
    error.value = "";
    result.value = null;
  },
);

function press(key: string): void {
  if (busy.value || result.value) return;
  sfx.pop();
  error.value = "";
  if (key === "back") phone.value = phone.value.slice(0, -1);
  else if (key === "clear") phone.value = "";
  else if (phone.value.length < 10) phone.value += key;
}

async function submit(): Promise<void> {
  if (!valid.value || busy.value) return;
  busy.value = true;
  try {
    result.value = await addLoyaltyStamp(props.sessionId, phone.value);
    sfx.chime();
  } catch (exc) {
    sfx.error();
    error.value = exc instanceof Error ? exc.message : String(exc);
  } finally {
    busy.value = false;
  }
}

function validUntil(value: string | null): string {
  if (!value) return "";
  const [year, month, day] = value.split("-");
  return `${day}.${month}.${year}`;
}
</script>

<template>
  <Transition name="dialog">
    <div v-if="open" class="dialog-backdrop" @pointerdown.self="emit('close')">
      <div class="dialog chrome-ring" role="dialog" aria-label="Tích điểm khách quen" style="width: 100rem">
        <div class="dialog-inner loyalty">
          <div class="loyalty-main">
            <div>
              <div class="mono muted">Khách quen</div>
              <div class="display loyalty-title">
                <template v-if="result?.reward_code"
                  >Bạn được tặng <span class="accent">1 lần chụp!</span></template
                >
                <template v-else-if="result"
                  >Đã tích <span class="accent">{{ result.stamps }} điểm</span></template
                >
                <template v-else>Tích điểm <span class="accent">mỗi lần chụp</span></template>
              </div>
            </div>
            <div class="loyalty-sub">
              <template v-if="result?.reward_code"
                >Đưa mã này ở màn thanh toán lần sau để chụp miễn phí.</template
              >
              <template v-else-if="result && !result.new_stamp">Phiên này đã được tích điểm rồi.</template>
              <template v-else-if="result">Còn {{ remaining }} lần nữa là được tặng một lần chụp.</template>
              <template v-else>Chụp đủ {{ target }} lần, lần tiếp theo được tặng.</template>
            </div>

            <div class="stamps" :aria-label="`${stampsShown} trên ${result?.target ?? target} điểm`">
              <span
                v-for="n in result?.target ?? target"
                :key="n"
                class="stamp"
                :class="{ on: n <= stampsShown, gift: n === (result?.target ?? target) }"
                :style="{ '--d': `${n * 70}ms` }"
              >
                <Icon v-if="n <= stampsShown" name="check" :size="24" :stroke="3" />
                <span v-else-if="n === (result?.target ?? target)" class="gift-label">QUÀ</span>
              </span>
            </div>

            <div v-if="result?.reward_code" class="reward">
              <span class="mono muted">Mã chụp miễn phí</span>
              <span class="display reward-code">{{ result.reward_code }}</span>
              <span class="mono muted">Dùng đến {{ validUntil(result.reward_valid_until) }}</span>
            </div>
            <template v-else-if="!result">
              <div class="phone-field" :class="{ bad: error }">
                <Icon name="phone" :size="24" />
                <span class="display phone-digits">{{ display }}</span>
                <span class="caret" />
                <span v-if="!phone" class="phone-placeholder">Số điện thoại</span>
              </div>
              <div class="mono" :class="error ? 'phone-error' : 'muted'" aria-live="polite">
                {{ error || "Chỉ dùng số điện thoại để tích điểm, không gửi quảng cáo" }}
              </div>
            </template>

            <div class="row-actions">
              <template v-if="result">
                <button class="btn btn-primary btn-md btn-arrowed" type="button" @click="emit('done')">
                  Xong
                  <span class="btn-arrow"><Icon name="arrow-right" :size="20" :stroke="2.6" /></span>
                </button>
              </template>
              <template v-else>
                <button class="btn btn-ghost btn-md" type="button" @click="emit('close')">Bỏ qua</button>
                <button
                  class="btn btn-primary btn-md btn-arrowed"
                  type="button"
                  :disabled="!valid || busy"
                  @click="submit"
                >
                  {{ busy ? "Đang lưu…" : "Tích điểm" }}
                  <span class="btn-arrow"><Icon name="arrow-right" :size="20" :stroke="2.6" /></span>
                </button>
              </template>
            </div>
          </div>

          <div v-if="!result" class="keypad">
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
          <div v-else class="loyalty-art">
            <span class="chrome-sphere floaty loyalty-sphere"
              ><Icon name="gift" :size="72" :stroke="1.8"
            /></span>
          </div>
        </div>
        <Star class="dialog-star" />
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.loyalty {
  align-items: center;
  display: flex;
  gap: 5.2rem;
  padding: 4.4rem 5rem;
}
.loyalty-main {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 2rem;
  min-width: 0;
}
.loyalty-title {
  font-size: 3.6rem;
  line-height: 1.15;
  margin-top: 0.6rem;
}
.loyalty-sub {
  color: var(--muted);
  font-size: 1.8rem;
  font-weight: 600;
}
.stamps {
  align-items: center;
  display: flex;
  gap: 1.2rem;
}
.stamp {
  align-items: center;
  background: #eef0f5;
  border: 2px dashed #b9bfcb;
  border-radius: 50%;
  color: #9aa0ae;
  display: flex;
  height: 5.2rem;
  justify-content: center;
  width: 5.2rem;
}
.stamp.on {
  animation: stamp-in 520ms var(--spring) both;
  animation-delay: var(--d);
  background: var(--cobalt);
  border: 0;
  color: var(--white);
}
.stamp.gift.on {
  background: var(--holo);
  color: var(--ink);
}
.gift-label {
  font-size: 1.1rem;
  font-weight: 800;
}
.phone-field {
  align-items: center;
  background: #f1f3f7;
  border: 2px solid var(--cobalt);
  border-radius: 3.8rem;
  color: var(--muted);
  display: flex;
  gap: 1.2rem;
  height: 7.6rem;
  padding: 0 2.6rem;
  position: relative;
}
.phone-field.bad {
  border-color: var(--red);
}
.phone-digits {
  color: var(--ink);
  font-size: 3rem;
  letter-spacing: 0.06em;
}
.phone-placeholder {
  color: #9aa0ae;
  font-size: 2.2rem;
  font-weight: 700;
  left: 7.4rem;
  position: absolute;
}
.phone-error {
  color: var(--red);
}
.caret {
  animation: blink 1s steps(2, start) infinite;
  background: var(--cobalt);
  height: 3.6rem;
  width: 3px;
}
.reward {
  background: var(--holo);
  border-radius: 3rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 2rem 2.6rem;
}
.reward-code {
  font-size: 4rem;
  letter-spacing: 0.06em;
}
.loyalty-art {
  display: flex;
  justify-content: center;
  width: 33rem;
}
.loyalty-sphere {
  align-items: center;
  color: var(--cobalt);
  display: flex;
  height: 24rem;
  justify-content: center;
  width: 24rem;
}
@keyframes stamp-in {
  from {
    opacity: 0;
    scale: 0.4;
  }
}
@keyframes blink {
  to {
    visibility: hidden;
  }
}
@media (orientation: portrait) {
  .loyalty {
    flex-direction: column;
  }
}
</style>
