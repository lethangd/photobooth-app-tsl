/** Shared motion tokens so every animation in the kiosk uses the same timings and curves. */

export const DURATION = { touch: 120, small: 240, enter: 400, page: 700 } as const;

export const EASE_IN = "cubic-bezier(0.16, 1, 0.3, 1)"; // "vào": fast then settles
export const EASE_OUT = "cubic-bezier(0.7, 0, 0.84, 0)"; // "ra": slow then whooshes away
// spring, stiffness 300 / damping 22 sampled into a linear() curve (~565 ms to settle)
export const SPRING =
  "linear(0, 0.027, 0.096, 0.194, 0.306, 0.424, 0.54, 0.649, 0.746, 0.831, 0.901, 0.958, 1.002, 1.034, 1.055, 1.069, 1.075, 1.075, 1.072, 1.066, 1.058, 1.049, 1.04, 1.032, 1.024, 1.017, 1.011, 1.006, 1.002, 0.999, 0.997, 0.995, 0.995, 0.994, 0.994, 0.995, 0.995, 0.996, 0.997, 0.997, 1)";

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export async function finished(animations: Animation[]): Promise<void> {
  await Promise.all(animations.map((animation) => animation.finished.catch(() => undefined)));
}

/**
 * Fly a copy of an image from one box to another (photo -> thumbnail slot and back).
 * Only transform/opacity are animated so it stays smooth on weak kiosk hardware.
 */
export async function flyImage(
  src: string,
  from: DOMRect,
  to: DOMRect,
  radius = "1.8rem",
  duration = 520,
): Promise<void> {
  if (!from.width || !to.width) return;
  const img = document.createElement("img");
  img.src = src;
  img.className = "fly-image";
  Object.assign(img.style, {
    left: `${from.left}px`,
    top: `${from.top}px`,
    width: `${from.width}px`,
    height: `${from.height}px`,
    borderRadius: radius,
  });
  document.body.appendChild(img);

  const dx = to.left + to.width / 2 - (from.left + from.width / 2);
  const dy = to.top + to.height / 2 - (from.top + from.height / 2);
  const scale = Math.min(to.width / from.width, to.height / from.height);
  const animation = img.animate(
    [
      { transform: "translate(0, 0) scale(1) rotate(0deg)", opacity: 1 },
      {
        transform: `translate(${dx * 0.55}px, ${dy * 0.45 - 40}px) scale(${(1 + scale) / 2}) rotate(-6deg)`,
        opacity: 1,
        offset: 0.55,
      },
      { transform: `translate(${dx}px, ${dy}px) scale(${scale}) rotate(0deg)`, opacity: 1 },
    ],
    { duration, easing: EASE_IN, fill: "forwards" },
  );
  await finished([animation]);
  img.remove();
}

/** Animate a number from `from` to `to`, calling `onValue` every frame (ease-out). */
export function countUp(
  from: number,
  to: number,
  duration: number,
  onValue: (value: number) => void,
): () => void {
  let frame = 0;
  const start = performance.now();
  const step = (now: number) => {
    const t = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - t, 3);
    onValue(Math.round(from + (to - from) * eased));
    if (t < 1) frame = requestAnimationFrame(step);
  };
  frame = requestAnimationFrame(step);
  return () => cancelAnimationFrame(frame);
}
