<script setup lang="ts">
const COLORS = ["#ff3d81", "#7c4dff", "#22d3ee", "#ffc857", "#ffffff", "#5eead4"];

// Deterministic pseudo-random pieces so the burst looks organic but never re-rolls on re-render.
const pieces = Array.from({ length: 46 }, (_, i) => {
  const seed = (n: number) => {
    const x = Math.sin(i * 97.13 + n * 31.7) * 10000;
    return x - Math.floor(x);
  };
  return {
    left: `${seed(1) * 100}%`,
    delay: `${seed(2) * 0.9}s`,
    duration: `${2.6 + seed(3) * 2.2}s`,
    drift: `${(seed(4) - 0.5) * 220}px`,
    spin: `${(seed(5) - 0.5) * 900}deg`,
    size: `${8 + seed(6) * 10}px`,
    color: COLORS[i % COLORS.length],
    round: seed(7) > 0.6,
  };
});
</script>

<template>
  <div class="confetti" aria-hidden="true">
    <i
      v-for="(piece, index) in pieces"
      :key="index"
      :class="{ round: piece.round }"
      :style="{
        left: piece.left,
        width: piece.size,
        height: piece.size,
        background: piece.color,
        animationDelay: piece.delay,
        animationDuration: piece.duration,
        '--drift': piece.drift,
        '--spin': piece.spin,
      }"
    />
  </div>
</template>
