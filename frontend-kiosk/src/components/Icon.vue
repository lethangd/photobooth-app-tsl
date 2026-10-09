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
  tag: ["M3 12V4h8l10 10-8 8z", "M7.5 8.5h.01"],
  phone: ["M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"],
  play: ["M8 5v14l11-7z"],
  undo: ["M9 14L4 9l5-5", "M4 9h11a5 5 0 0 1 0 10h-3"],
  trash: ["M4 7h16", "M10 11v6", "M14 11v6", "M6 7l1 13h10l1-13", "M9 7V4h6v3"],
  pen: ["M4 20l4-1L19 8l-3-3L5 16z", "M14 7l3 3"],
  type: ["M5 6V4h14v2", "M12 4v16", "M9 20h6"],
  smile: ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z", "M8.5 14a4.5 4.5 0 0 0 7 0", "M9 9.5h.01", "M15 9.5h.01"],
  clock: ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z", "M12 7v5l3 2"],
  download: ["M12 4v11", "M7 10l5 5 5-5", "M5 20h14"],
  headset: ["M4 14v-2a8 8 0 0 1 16 0v2", "M4 14h3v6H5a1 1 0 0 1-1-1z", "M20 14h-3v6h2a1 1 0 0 0 1-1z"],
  gift: ["M4 10h16v4H4z", "M6 14h12v7H6z", "M12 10v11", "M12 10C9 10 7 8 8 6s4 0 4 4c0-4 3-6 4-4s-1 4-4 4"],
  minus: ["M5 12h14"],
  plus: ["M12 5v14", "M5 12h14"],
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
