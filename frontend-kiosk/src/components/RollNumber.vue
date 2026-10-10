<script setup lang="ts">
/** Price that rolls digit by digit to a new value, like a mechanical counter. */
import { computed } from "vue";

const props = defineProps<{ value: number; suffix?: string }>();

const chars = computed(() => [...new Intl.NumberFormat("vi-VN").format(props.value)]);
const DIGITS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9];
</script>

<template>
  <span class="roll" :aria-label="`${chars.join('')}${suffix ?? ''}`">
    <template v-for="(char, index) in chars" :key="chars.length - index">
      <span v-if="/\d/.test(char)" class="roll-col" aria-hidden="true">
        <span
          class="roll-strip"
          :style="{
            transform: `translateY(${-Number(char)}em)`,
            transitionDelay: `${(chars.length - index) * 45}ms`,
          }"
        >
          <span v-for="digit in DIGITS" :key="digit">{{ digit }}</span>
        </span>
      </span>
      <span v-else aria-hidden="true">{{ char }}</span>
    </template>
    <span v-if="suffix" aria-hidden="true">{{ suffix }}</span>
  </span>
</template>

<style scoped>
.roll {
  display: inline-flex;
  line-height: 1;
}
.roll-col {
  display: inline-block;
  height: 1em;
  overflow: hidden;
}
.roll-strip {
  display: flex;
  flex-direction: column;
  transition: transform 640ms var(--spring);
}
.roll-strip span {
  height: 1em;
  text-align: center;
}
:global(.reduced) .roll-strip {
  transition-duration: 1ms;
}
</style>
