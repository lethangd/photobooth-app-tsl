<script setup lang="ts">
defineProps<{ color?: string }>();
</script>

<template>
  <svg class="star" viewBox="0 0 24 24" aria-hidden="true">
    <path
      d="M12 0 C13 8 16 11 24 12 C16 13 13 16 12 24 C11 16 8 13 0 12 C8 11 11 8 12 0 Z"
      :fill="color ?? '#2B3BFF'"
    />
  </svg>
</template>
