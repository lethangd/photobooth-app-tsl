<script setup lang="ts">
import Icon from "./Icon.vue";

const STEPS = ["01 Khung", "02 Thanh toán", "03 Chụp", "04 Chọn ảnh", "05 Màu & viền", "06 In ảnh"];

defineProps<{ step: number; pill?: string; pillTone?: "ready" | "rec" | "holo"; closable?: boolean }>();
const emit = defineEmits<{ close: [] }>();
</script>

<template>
  <header class="topbar">
    <div class="brand">
      <span class="chrome-sphere brand-sphere" />
      <span class="display brand-name">TSL</span>
      <span class="mono holo brand-tag">photobooth</span>
    </div>

    <nav class="steps" :class="{ hidden: step < 0 }" aria-label="Tiến trình">
      <template v-for="(label, index) in STEPS" :key="label">
        <span v-if="index > 0" class="step-line" />
        <span class="step mono" :class="{ done: index < step, active: index === step }">
          <i v-if="index < step" class="step-dot" />
          <span class="step-label">{{ label }}</span>
        </span>
      </template>
    </nav>

    <div class="topbar-end">
      <span v-if="pill" class="pill mono" :class="pillTone ? `pill--${pillTone}` : ''">
        <i v-if="pillTone === 'ready' || pillTone === 'rec'" class="pill-dot" />
        {{ pill }}
      </span>
      <button v-if="closable" class="icon-btn" type="button" aria-label="Về màn chờ" @click="emit('close')">
        <Icon name="x" :size="22" />
      </button>
    </div>
  </header>
</template>
