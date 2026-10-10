<script setup lang="ts">
/**
 * The page transitions of the kiosk. Each variant covers the screen, calls `swap()` while
 * everything is hidden (the page underneath changes there), then reveals the new page:
 *   - wipe:    "Holo Wipe", default for the ordinary steps: a wide diagonal foil band sweeps across
 *   - flash:   "Flash Cut", the big moments (start shooting, print done): white flash, glow, thick grain
 *   - capsule: "Capsule Rush", the first, bouncier style (kept, not used by default any more)
 *   - bubble:  "Bubble Pop", success moments (payment approved, PIN ok, print done)
 *   - shutter: "Shutter Blocks", only around the capture screen
 *   - fade:    used for everything when reduced motion is on
 */
import { ref } from "vue";

import { EASE_IN, EASE_OUT, finished, sleep } from "@/lib/motion";
import * as sfx from "@/lib/sfx";

type Swap = () => void | Promise<void>;

const props = defineProps<{ reduced: boolean }>();

const active = ref(false);
const rush = ref<HTMLElement | null>(null);
const capsules = ref<HTMLElement[]>([]);
const bubbleEl = ref<HTMLElement | null>(null);
const checkEl = ref<HTMLElement | null>(null);
const drops = ref<HTMLElement[]>([]);
const blocksTop = ref<HTMLElement[]>([]);
const blocksBottom = ref<HTMLElement[]>([]);
const flashEl = ref<HTMLElement | null>(null);
const fadeEl = ref<HTMLElement | null>(null);
const wipeEl = ref<HTMLElement | null>(null);
const pills = ref<HTMLElement[]>([]);
const cutEl = ref<HTMLElement | null>(null);
const cutGlow = ref<HTMLElement | null>(null);

// relative capsule sizes so the rush does not look mechanical
const SIZE_VARIANCE = [0.2, 0.9, 0.45, 1, 0.3, 0.75];
const BACK_CAPSULES = [1, 2, 4, 5];

let running = false;

function reset(elements: (HTMLElement | null)[]): void {
  for (const el of elements) el?.getAnimations().forEach((animation) => animation.cancel());
}

async function run(body: () => Promise<void>): Promise<boolean> {
  if (running) return false;
  running = true;
  active.value = true;
  // ambient loops pause while the screen changes, so the transition never stutters
  document.documentElement.classList.add("tx-running");
  try {
    await body();
  } finally {
    active.value = false;
    running = false;
    document.documentElement.classList.remove("tx-running");
  }
  return true;
}

/** Holo Wipe: a wide diagonal foil band sweeps across; the old page goes behind it, the new one comes out. */
async function wipe(swap: Swap, dir: 1 | -1 = 1): Promise<boolean> {
  if (props.reduced) return fade(swap);
  return run(async () => {
    const band = wipeEl.value;
    if (!band) return void (await swap());
    reset([band, ...pills.value]);
    const w = window.innerWidth;
    const h = window.innerHeight;
    const width = w * 1.5 + h * 0.4;
    Object.assign(band.style, { width: `${width}px`, left: `${(w - width) / 2}px` });
    const off = (w + width) / 2 + h * 0.4;
    const easeCover = "cubic-bezier(0.55, 0, 0.35, 1)";

    sfx.whoosh();
    const cover = [
      band.animate(
        [
          { transform: `translateX(${dir * off}px) skewX(-18deg)` },
          { transform: "translateX(0) skewX(-18deg)" },
        ],
        {
          duration: 300,
          easing: easeCover,
          fill: "both",
        },
      ),
      ...pills.value.map((pill, i) =>
        pill.animate(
          [
            {
              transform: `translateX(${dir * (off + 160 + i * 90)}px) rotate(${-20 + i * 14}deg)`,
              opacity: 1,
            },
            { transform: `translateX(${dir * (40 + i * 30)}px) rotate(${-10 + i * 12}deg)`, opacity: 1 },
          ],
          { duration: 330, delay: 40 + i * 30, easing: easeCover, fill: "both" },
        ),
      ),
    ];
    await finished([cover[0]]);
    await swap();
    await sleep(40);
    await finished([
      band.animate(
        [
          { transform: "translateX(0) skewX(-18deg)" },
          { transform: `translateX(${-dir * off}px) skewX(-18deg)` },
        ],
        {
          duration: 320,
          easing: easeCover,
          fill: "both",
        },
      ),
      ...pills.value.map((pill, i) =>
        pill.animate(
          [
            { transform: `translateX(${dir * (40 + i * 30)}px) rotate(${-10 + i * 12}deg)`, opacity: 1 },
            {
              transform: `translateX(${-dir * (off + 220 + i * 120)}px) rotate(${10 + i * 10}deg)`,
              opacity: 0.6,
            },
          ],
          { duration: 380, delay: i * 35, easing: easeCover, fill: "both" },
        ),
      ),
    ]);
    cover.forEach((animation) => animation.cancel());
  });
}

/** Flash Cut: a white flash of ~80 ms, light spreads from the middle, the new page shows with thick grain. */
async function flash(swap: Swap): Promise<boolean> {
  if (props.reduced) return fade(swap);
  return run(async () => {
    const white = cutEl.value;
    const glow = cutGlow.value;
    if (!white || !glow) return void (await swap());
    reset([white, glow]);
    sfx.flash();
    await finished([
      white.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 40, easing: "linear", fill: "forwards" }),
    ]);
    await swap();
    await sleep(80);
    const app = document.querySelector(".app");
    app?.classList.add("grain-burst");
    window.setTimeout(() => app?.classList.remove("grain-burst"), 300);
    await finished([
      white.animate([{ opacity: 1 }, { opacity: 0 }], {
        duration: 260,
        easing: "ease-out",
        fill: "forwards",
      }),
      glow.animate(
        [
          { opacity: 0.95, transform: "translate(-50%, -50%) scale(0.2)" },
          { opacity: 0, transform: "translate(-50%, -50%) scale(1.6)" },
        ],
        { duration: 520, easing: "cubic-bezier(0.2, 0.7, 0.3, 1)", fill: "forwards" },
      ),
    ]);
  });
}

async function fade(swap: Swap): Promise<boolean> {
  return run(async () => {
    const el = fadeEl.value;
    if (!el) return void (await swap());
    reset([el]);
    await finished([
      el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 140, easing: "ease-out", fill: "forwards" }),
    ]);
    await swap();
    await finished([
      el.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 180, easing: "ease-in", fill: "forwards" }),
    ]);
  });
}

/** dir 1 = forward (blocks fly in from the right and leave to the left), -1 = back. */
async function capsule(swap: Swap, dir: 1 | -1 = 1): Promise<boolean> {
  if (props.reduced) return fade(swap);
  return run(async () => {
    const wrap = rush.value;
    if (!wrap) return void (await swap());
    const back = dir === -1;
    const used = back ? BACK_CAPSULES.map((i) => capsules.value[i]) : capsules.value;
    reset(capsules.value);

    const w = window.innerWidth;
    const h = window.innerHeight;
    const side = Math.hypot(w, h) * 1.1;
    Object.assign(wrap.style, {
      width: `${side}px`,
      height: `${side}px`,
      left: `${(w - side) / 2}px`,
      top: `${(h - side) / 2}px`,
    });

    const row = side / used.length;
    const width = side * 1.35;
    const travel = side / 2 + width / 2 + 40;
    capsules.value.forEach((el) => (el.style.display = "none"));
    used.forEach((el, i) => {
      const height = row * (1.35 + 0.3 * SIZE_VARIANCE[i % SIZE_VARIANCE.length]);
      Object.assign(el.style, {
        display: "block",
        width: `${width}px`,
        height: `${height}px`,
        left: `${(side - width) / 2}px`,
        top: `${i * row + row / 2 - height / 2}px`,
      });
    });

    const inDuration = back ? 170 : 230;
    const stagger = back ? 22 : 28;
    sfx.whoosh();
    await finished(
      used.map((el, i) =>
        el.animate([{ transform: `translateX(${dir * travel}px)` }, { transform: "translateX(0)" }], {
          duration: inDuration,
          delay: i * stagger,
          easing: EASE_IN,
          fill: "both",
        }),
      ),
    );
    await swap();
    await sleep(back ? 50 : 80);
    await finished(
      used.map((el, i) =>
        el.animate([{ transform: "translateX(0)" }, { transform: `translateX(${-dir * travel}px)` }], {
          duration: inDuration,
          delay: i * stagger,
          easing: EASE_OUT,
          fill: "both",
        }),
      ),
    );
  });
}

/** Chrome bubble grows from `origin` (the button just pressed), optional ✓, then pops into small spheres. */
async function bubble(swap: Swap, origin?: { x: number; y: number }, check = true): Promise<boolean> {
  if (props.reduced) return fade(swap);
  return run(async () => {
    const el = bubbleEl.value;
    const tick = checkEl.value;
    if (!el || !tick) return void (await swap());
    reset([el, tick, ...drops.value]);

    const w = window.innerWidth;
    const h = window.innerHeight;
    const x = origin?.x ?? w / 2;
    const y = origin?.y ?? h / 2;
    const radius =
      Math.max(Math.hypot(x, y), Math.hypot(w - x, y), Math.hypot(x, h - y), Math.hypot(w - x, h - y)) + 24;
    Object.assign(el.style, {
      width: `${radius * 2}px`,
      height: `${radius * 2}px`,
      left: `${x - radius}px`,
      top: `${y - radius}px`,
    });

    const grow = el.animate([{ transform: "scale(0)" }, { transform: "scale(1)" }], {
      duration: 360,
      easing: EASE_IN,
      fill: "both",
    });
    const steps: Animation[] = [grow];
    if (check) {
      sfx.chime();
      steps.push(
        tick.animate(
          [
            { transform: "translate(-50%, -50%) scale(0)", opacity: 0 },
            { transform: "translate(-50%, -50%) scale(1.2)", opacity: 1, offset: 0.6 },
            { transform: "translate(-50%, -50%) scale(1)", opacity: 1 },
          ],
          { duration: 260, delay: 200, easing: "ease-out", fill: "both" },
        ),
      );
    }
    await finished(steps);
    await swap();

    sfx.pop();
    const burst: Animation[] = [
      el.animate(
        [
          { opacity: 1, transform: "scale(1)" },
          { opacity: 0, transform: "scale(1.04)" },
        ],
        { duration: 200, easing: "ease-out", fill: "both" },
      ),
    ];
    if (check) {
      burst.push(
        tick.animate(
          [
            { transform: "translate(-50%, -50%) scale(1)", opacity: 1 },
            { transform: "translate(-50%, -50%) scale(0.6)", opacity: 0 },
          ],
          { duration: 200, easing: EASE_OUT, fill: "both" },
        ),
      );
    }
    const distance = Math.max(w, h) * 0.6;
    drops.value.forEach((drop, i) => {
      const angle = (i / drops.value.length) * Math.PI * 2 + (i % 2 ? 0.25 : -0.1);
      const reach = distance * (0.7 + (i % 3) * 0.15);
      burst.push(
        drop.animate(
          [
            { transform: "translate(-50%, -50%) scale(0.9)", opacity: 1 },
            {
              transform: `translate(calc(-50% + ${Math.cos(angle) * reach}px), calc(-50% + ${Math.sin(angle) * reach}px)) scale(0.25)`,
              opacity: 0,
            },
          ],
          { duration: 420, easing: "cubic-bezier(0.2, 0.7, 0.3, 1)", fill: "both" },
        ),
      );
    });
    await finished(burst);
  });
}

/** Camera-shutter blocks close from top and bottom, one short white flash, then open. */
async function shutter(swap?: Swap): Promise<boolean> {
  if (props.reduced) return fade(swap ?? (() => undefined));
  return run(async () => {
    const tops = blocksTop.value;
    const bottoms = blocksBottom.value;
    const flash = flashEl.value;
    reset([...tops, ...bottoms, flash]);
    const delays = [0, 35, 70, 105];

    const close = [
      ...tops.map((el, i) =>
        el.animate([{ transform: "translateY(-102%)" }, { transform: "translateY(0)" }], {
          duration: 220,
          delay: delays[i],
          easing: EASE_IN,
          fill: "both",
        }),
      ),
      ...bottoms.map((el, i) =>
        el.animate([{ transform: "translateY(102%)" }, { transform: "translateY(0)" }], {
          duration: 220,
          delay: delays[i],
          easing: EASE_IN,
          fill: "both",
        }),
      ),
    ];
    await finished(close);
    sfx.shutter();
    if (flash)
      flash.animate([{ opacity: 0 }, { opacity: 0.9 }, { opacity: 0 }], {
        duration: 120,
        easing: "linear",
        fill: "both",
      });
    await swap?.();
    await sleep(100);
    await finished([
      ...tops.map((el, i) =>
        el.animate([{ transform: "translateY(0)" }, { transform: "translateY(-102%)" }], {
          duration: 220,
          delay: delays[i],
          easing: EASE_OUT,
          fill: "both",
        }),
      ),
      ...bottoms.map((el, i) =>
        el.animate([{ transform: "translateY(0)" }, { transform: "translateY(102%)" }], {
          duration: 220,
          delay: delays[i],
          easing: EASE_OUT,
          fill: "both",
        }),
      ),
    ]);
  });
}

function isRunning(): boolean {
  return running;
}

defineExpose({ wipe, flash, capsule, bubble, shutter, fade, isRunning });
</script>

<template>
  <div class="tx" :class="{ active }" aria-hidden="true">
    <div ref="rush" class="tx-rush">
      <div v-for="i in 6" :key="i" ref="capsules" class="tx-capsule" :class="`tx-capsule--${i}`">
        <svg v-if="i === 6" class="tx-star" viewBox="0 0 24 24">
          <path d="M12 0 C13 8 16 11 24 12 C16 13 13 16 12 24 C11 16 8 13 0 12 C8 11 11 8 12 0 Z" />
        </svg>
      </div>
    </div>

    <div ref="bubbleEl" class="tx-bubble" />
    <div v-for="i in 9" :key="`d${i}`" ref="drops" class="tx-drop" />
    <div ref="checkEl" class="tx-check">
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.8"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="M5 12.5l4.5 4.5L19 7.5" />
      </svg>
    </div>

    <div class="tx-shutter">
      <div v-for="i in 4" :key="`s${i}`" class="tx-col">
        <div ref="blocksTop" class="tx-block tx-block--top" :class="{ cobalt: i % 2 === 0 }" />
        <div ref="blocksBottom" class="tx-block tx-block--bottom" :class="{ cobalt: i % 2 === 1 }" />
      </div>
    </div>
    <div ref="wipeEl" class="tx-wipe" />
    <div v-for="i in 3" :key="`p${i}`" ref="pills" class="tx-pill" :class="`tx-pill--${i}`" />
    <div ref="cutEl" class="tx-cut" />
    <div ref="cutGlow" class="tx-cut-glow" />
    <div ref="flashEl" class="tx-flash" />
    <div ref="fadeEl" class="tx-fade" />
  </div>
</template>
