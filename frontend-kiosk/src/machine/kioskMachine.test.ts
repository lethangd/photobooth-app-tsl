import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createActor, fromPromise } from "xstate";

import type { KioskConfig } from "@/api/types";

import { kioskMachine } from "./kioskMachine";

const config: KioskConfig = {
  package_select_timeout_seconds: 6,
  shot_buffer_count: 2,
  countdown_seconds: 1,
  get_ready_seconds: 1,
  payment_mock_seconds: 1,
  photo_select_warn_seconds: 2,
  photo_select_grace_seconds: 1,
  filter_select_warn_seconds: 2,
  filter_select_grace_seconds: 1,
  final_preview_timeout_seconds: 3,
  printing_mock_seconds: 1,
  qr_download_seconds: 2,
  thank_you_seconds: 1,
  digital_delivery_default_enabled: true,
  digital_delivery_retention_days: 7,
  timelapse_render_mock_seconds: 6,
  filters: [{ id: "natural", name: "Natural", css_filter: "none" }],
  frame_types: [{ slot_count: 2, shots_to_take: 4, price: 50000, templates: [] }],
};

function makeActor(overrides: Parameters<typeof kioskMachine.provide>[0] = {}) {
  const autoSelectPhotos = vi.fn();
  const resetSession = vi.fn();
  const machine = kioskMachine.provide({
    actions: { autoSelectPhotos, resetSession, keepCurrentTemplate: () => {} },
    actors: {
      captureSequence: fromPromise(async () => {}),
      renderCollage: fromPromise(async () => {}),
    },
    ...overrides,
  });
  const actor = createActor(machine, { input: { config } });
  return { actor, autoSelectPhotos, resetSession };
}

describe("kioskMachine", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("walks the full S1–S12 happy path back to idle", async () => {
    const { actor } = makeActor();
    actor.start();
    expect(actor.getSnapshot().value).toBe("idle");

    actor.send({ type: "START" });
    expect(actor.getSnapshot().value).toBe("packageSelect");

    actor.send({ type: "SELECT_PACKAGE" });
    expect(actor.getSnapshot().value).toBe("payment");

    await vi.advanceTimersByTimeAsync(1000); // paymentMock
    expect(actor.getSnapshot().value).toBe("getReady");

    await vi.advanceTimersByTimeAsync(1000); // getReady
    // capturing invokes captureSequence which resolves immediately
    expect(actor.getSnapshot().value).toEqual({ photoSelect: "active" });

    actor.send({ type: "NEXT" });
    expect(actor.getSnapshot().value).toEqual({ filterSelect: "active" });

    actor.send({ type: "NEXT" });
    expect(actor.getSnapshot().value).toEqual({ frameSelect: "active" });

    actor.send({ type: "NEXT" });
    expect(actor.getSnapshot().value).toBe("finalPreview");

    actor.send({ type: "PRINT" });
    // printing.rendering -> renderCollage resolves -> printing.settling
    await vi.advanceTimersByTimeAsync(0);
    expect(actor.getSnapshot().value).toEqual({ printing: "settling" });

    await vi.advanceTimersByTimeAsync(1000); // printingMock
    expect(actor.getSnapshot().value).toBe("qrDownload");

    await vi.advanceTimersByTimeAsync(2000); // qrDownload
    expect(actor.getSnapshot().value).toBe("thankYou");

    await vi.advanceTimersByTimeAsync(1000); // thankYou
    expect(actor.getSnapshot().value).toBe("idle");
  });

  it("resets to idle on a pre-payment timeout", async () => {
    const { actor, resetSession } = makeActor();
    actor.start();
    actor.send({ type: "START" });
    actor.send({ type: "SELECT_PACKAGE" });
    actor.send({ type: "RESET" });
    expect(actor.getSnapshot().value).toBe("packageSelect");

    await vi.advanceTimersByTimeAsync(6000); // packageTimeout
    expect(actor.getSnapshot().value).toBe("idle");
    expect(resetSession).toHaveBeenCalled();
  });

  it("auto-advances with defaults after payment (photoSelect warn + grace)", async () => {
    const { actor, autoSelectPhotos } = makeActor();
    actor.start();
    actor.send({ type: "START" });
    actor.send({ type: "SELECT_PACKAGE" });
    await vi.advanceTimersByTimeAsync(1000); // payment
    await vi.advanceTimersByTimeAsync(1000); // getReady -> capturing -> photoSelect
    expect(actor.getSnapshot().value).toEqual({ photoSelect: "active" });

    await vi.advanceTimersByTimeAsync(2000); // warn
    expect(actor.getSnapshot().value).toEqual({ photoSelect: "warning" });

    await vi.advanceTimersByTimeAsync(1000); // grace
    expect(actor.getSnapshot().value).toEqual({ filterSelect: "active" });
    expect(autoSelectPhotos).toHaveBeenCalled();
  });

  it("blocks NEXT out of photoSelect when the selection is incomplete", async () => {
    const { actor } = makeActor({ guards: { hasExactSelection: () => false } });
    actor.start();
    actor.send({ type: "START" });
    actor.send({ type: "SELECT_PACKAGE" });
    await vi.advanceTimersByTimeAsync(2000);
    expect(actor.getSnapshot().value).toEqual({ photoSelect: "active" });
    actor.send({ type: "NEXT" });
    expect(actor.getSnapshot().value).toEqual({ photoSelect: "active" });
  });

  it("routes a camera failure to error and RETRY resumes capturing", async () => {
    const { actor } = makeActor({
      actors: {
        captureSequence: fromPromise(async (): Promise<void> => {
          throw new Error("camera offline");
        }),
        renderCollage: fromPromise(async () => {}),
      },
    });
    actor.start();
    actor.send({ type: "START" });
    actor.send({ type: "SELECT_PACKAGE" });
    await vi.advanceTimersByTimeAsync(1000); // payment
    await vi.advanceTimersByTimeAsync(1000); // getReady -> capturing -> (reject) -> error
    expect(actor.getSnapshot().value).toBe("error");
    expect(actor.getSnapshot().context.error).toBe("camera offline");

    actor.send({ type: "RETRY" });
    expect(actor.getSnapshot().value).toBe("capturing");
  });

  it("still reaches the QR screen when rendering fails", async () => {
    const { actor } = makeActor({
      actors: {
        captureSequence: fromPromise(async () => {}),
        renderCollage: fromPromise<void>(async () => {
          throw new Error("render failed");
        }),
      },
    });
    actor.start();
    actor.send({ type: "START" });
    actor.send({ type: "SELECT_PACKAGE" });
    await vi.advanceTimersByTimeAsync(2000);
    expect(actor.getSnapshot().value).toEqual({ photoSelect: "active" });
    actor.send({ type: "NEXT" });
    actor.send({ type: "NEXT" });
    actor.send({ type: "NEXT" });
    actor.send({ type: "PRINT" });
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(1000); // printingMock
    expect(actor.getSnapshot().value).toBe("qrDownload");
  });

  it("auto-confirms and prints when finalPreview times out", async () => {
    const { actor } = makeActor();
    actor.start();
    actor.send({ type: "START" });
    actor.send({ type: "SELECT_PACKAGE" });
    await vi.advanceTimersByTimeAsync(2000);
    actor.send({ type: "NEXT" });
    actor.send({ type: "NEXT" });
    actor.send({ type: "NEXT" });
    expect(actor.getSnapshot().value).toBe("finalPreview");
    await vi.advanceTimersByTimeAsync(3000); // finalPreviewTimeout
    expect(actor.getSnapshot().value).toHaveProperty("printing");
  });
});
