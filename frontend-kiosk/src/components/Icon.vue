<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{ name: string; size?: number }>();

const PATHS: Record<string, string[]> = {
  "arrow-right": ["M5 12h14", "M13 6l6 6-6 6"],
  "arrow-left": ["M19 12H5", "M11 6l-6 6 6 6"],
  check: ["M5 12.5l4.5 4.5L19 7.5"],
  camera: [
    "M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z",
    "M12 17a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z",
  ],
  refresh: ["M20 11a8 8 0 1 0-2.3 5.7", "M20 4v7h-7"],
  printer: [
    "M7 9V4h10v5",
    "M7 17H5a1 1 0 0 1-1-1v-6a1 1 0 0 1 1-1h14a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1h-2",
    "M7 14h10v6H7z",
  ],
  sparkle: [
    "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z",
    "M19 16l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z",
  ],
  video: ["M4 6h11a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1z", "M16 10l5-3v10l-5-3"],
  home: ["M4 11l8-7 8 7", "M6 10v10h12V10"],
  heart: ["M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"],
  touch: [
    "M9 11V5a2 2 0 1 1 4 0v6",
    "M13 11V9.5a2 2 0 0 1 4 0V15a6 6 0 0 1-6 6h-1a6 6 0 0 1-5.2-3L3 13.5a1.7 1.7 0 0 1 2.8-1.8L9 14",
  ],
  alert: ["M12 4l9 16H3z", "M12 10v4", "M12 17.5v.01"],
  qr: [
    "M4 4h6v6H4z",
    "M14 4h6v6h-6z",
    "M4 14h6v6H4z",
    "M14 14h3v3h-3z",
    "M20 14v.01",
    "M14 20h3",
    "M20 17v3",
  ],
};

const paths = computed(() => PATHS[props.name] ?? []);
</script>

<template>
  <svg
    class="icon"
    :width="size ?? 24"
    :height="size ?? 24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2.2"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path v-for="d in paths" :key="d" :d="d" />
  </svg>
</template>
