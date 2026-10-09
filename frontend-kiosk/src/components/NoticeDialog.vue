<script setup lang="ts">
/**
 * Chrome-framed dialog of the kiosk designs (03d QR expired, 03e short transfer, 05c still there?, …):
 * a round badge, a title, a text and the actions. `aside` puts extra content (a QR, a keypad) on the right.
 */
import Icon from "./Icon.vue";
import Star from "./Star.vue";

withDefaults(
  defineProps<{
    open: boolean;
    title: string;
    text?: string;
    icon?: string;
    tone?: "cobalt" | "red" | "amber";
    width?: number;
    label?: string;
    /** tapping outside the dialog closes it */
    dismissable?: boolean;
  }>(),
  { text: "", icon: "alert", tone: "cobalt", width: 64, label: "", dismissable: false },
);
const emit = defineEmits<{ close: [] }>();
</script>

<template>
  <Transition name="dialog">
    <div v-if="open" class="dialog-backdrop" @pointerdown.self="dismissable && emit('close')">
      <div
        class="dialog chrome-ring notice"
        :style="{ width: `${width}rem` }"
        role="alertdialog"
        :aria-label="label || title"
      >
        <div class="dialog-inner notice-inner" :class="{ split: $slots.aside }">
          <div class="notice-main" :class="{ center: !$slots.aside }">
            <slot name="badge">
              <span class="notice-badge" :class="`tone-${tone}`"
                ><Icon :name="icon" :size="40" :stroke="2.6"
              /></span>
            </slot>
            <div>
              <div class="display notice-title">{{ title }}</div>
              <div v-if="text" class="notice-text">{{ text }}</div>
            </div>
            <slot />
            <div v-if="$slots.actions" class="row-actions notice-actions"><slot name="actions" /></div>
          </div>
          <div v-if="$slots.aside" class="notice-aside"><slot name="aside" /></div>
        </div>
        <Star class="dialog-star" />
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.notice-inner {
  padding: 4.4rem 5rem;
}
.notice-inner.split {
  align-items: center;
  display: flex;
  gap: 4.4rem;
}
.notice-main {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 2rem;
  min-width: 0;
}
.notice-main.center {
  align-items: center;
  text-align: center;
}
.notice-aside {
  align-items: center;
  display: flex;
  flex: none;
  flex-direction: column;
  gap: 1.2rem;
}
.notice-badge {
  align-items: center;
  border-radius: 50%;
  color: var(--white);
  display: flex;
  flex: none;
  height: 8.4rem;
  justify-content: center;
  width: 8.4rem;
}
.tone-cobalt {
  background: var(--cobalt);
  box-shadow: 0 0 0 1.2rem #eef0ff;
}
.tone-red {
  background: var(--red);
  box-shadow: 0 0 0 1.2rem #ffe8ea;
}
.tone-amber {
  background: #f59e0b;
  box-shadow: 0 0 0 1.2rem #fff4de;
}
.notice-title {
  font-size: 3.6rem;
  line-height: 1.15;
}
.notice-text {
  color: var(--muted);
  font-size: 1.9rem;
  font-weight: 600;
  line-height: 1.5;
  margin-top: 1rem;
  white-space: pre-line;
}
.notice-actions {
  margin-top: 0.6rem;
}
@media (orientation: portrait) {
  .notice {
    max-width: 84rem;
  }
  .notice-inner.split {
    flex-direction: column;
  }
}
</style>
