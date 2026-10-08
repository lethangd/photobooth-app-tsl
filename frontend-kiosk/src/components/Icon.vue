<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{ name: string; size?: number; stroke?: number }>();

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
  lock: [
    "M7 11h10a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2z",
    "M8 11V7a4 4 0 0 1 8 0v4",
  ],
  backspace: ["M21 5H9l-6 7 6 7h12z", "M17 9l-6 6", "M11 9l6 6"],
  x: ["M6 6l12 12", "M18 6L6 18"],
  home: ["M4 11l8-7 8 7", "M6 10v10h12V10"],
  alert: ["M12 7v6", "M12 17v.01"],
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
    :stroke-width="stroke ?? 2.2"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path v-for="d in paths" :key="d" :d="d" />
  </svg>
</template>
