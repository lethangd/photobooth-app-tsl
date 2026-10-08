<script setup lang="ts">
/**
 * White printed photo strip ("TSL" footer, star sticker in the corner). Shows `photos`
 * in a 1-column strip, or a 2×2 grid for 4-photo layouts. Missing photos become
 * dashed numbered slots, used while the guest is still picking.
 */
import { computed } from "vue";

import Star from "./Star.vue";

const props = defineProps<{
  photos: (string | null | undefined)[];
  slots?: number;
  footer?: string;
  filter?: string;
  slotRefs?: (el: Element | null, index: number) => void;
}>();

const count = computed(() => props.slots ?? props.photos.length);
const grid = computed(() => count.value === 4);
const items = computed(() => Array.from({ length: count.value }, (_, i) => props.photos[i] ?? null));
</script>

<template>
  <div class="strip" :class="{ 'strip--grid': grid }">
    <div class="strip-photos">
      <div
        v-for="(photo, index) in items"
        :key="index"
        :ref="(el) => slotRefs?.(el as Element | null, index)"
        class="strip-cell"
      >
        <img v-if="photo" :src="photo" alt="" :style="filter ? { filter } : undefined" />
        <span v-else class="strip-empty">{{ String(index + 1).padStart(2, "0") }}</span>
      </div>
    </div>
    <div class="strip-foot">{{ footer ?? "TSL" }}</div>
    <Star class="strip-star" />
  </div>
</template>
