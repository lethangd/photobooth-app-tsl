import { assign, fromPromise, setup } from "xstate";

import type { KioskConfig } from "@/api/types";

export type KioskInput = { config: KioskConfig };

export interface KioskContext {
  config: KioskConfig;
  error: string | null;
  /** which state should RETRY resume from */
  retryTarget: "capturing" | null;
}

export type KioskEvent =
  | { type: "START" }
  | { type: "SELECT_PACKAGE" }
  | { type: "PAYMENT_CONFIRMED" }
  | { type: "START_CAPTURE" }
  | { type: "CAPTURE_DONE" }
  | { type: "CAPTURE_FAILED"; message: string }
  | { type: "RETAKE" }
  | { type: "NEXT" }
  | { type: "BACK" }
  | { type: "EDIT" }
  | { type: "PRINT" }
  | { type: "FINISH" }
  | { type: "RETRY" }
  | { type: "RESET" };

const seconds = (value: number) => Math.max(0, value) * 1000;

/**
 * Kiosk navigation state chart (spec S1–S12).
 *
 * Side effects are declared as named actions/actors and left as no-ops here;
 * `App.vue` provides the real implementations (wired to the Pinia session store
 * + the framebooth API) via `kioskMachine.provide({...})`. Tests provide mocks.
 */
export const kioskMachine = setup({
  types: {
    context: {} as KioskContext,
    events: {} as KioskEvent,
    input: {} as KioskInput,
  },
  actors: {
    // Runs the full N+buffer capture sequence. Resolves when every shot is stored.
    // App.vue provides the real implementation (closure over the session store).
    captureSequence: fromPromise(async (): Promise<void> => {}),
    // Renders the final collage + creates the gallery media item.
    renderCollage: fromPromise(async (): Promise<void> => {}),
  },
  actions: {
    resetSession: () => {},
    autoSelectPhotos: () => {},
    keepCurrentTemplate: () => {},
    assignError: assign({
      error: ({ event }) => {
        if ("message" in event && typeof event.message === "string") return event.message;
        if ("error" in event) {
          const cause = (event as { error: unknown }).error;
          return cause instanceof Error ? cause.message : String(cause);
        }
        return "unknown error";
      },
    }),
    clearError: assign({ error: null, retryTarget: null }),
    markRetryCapture: assign({ retryTarget: "capturing" as const }),
  },
  guards: {
    // Overridden by App with a store-backed check; default allows progress.
    hasExactSelection: () => true,
  },
  delays: {
    packageTimeout: ({ context }) => seconds(context.config.package_select_timeout_seconds),
    paymentMock: ({ context }) => seconds(context.config.payment_mock_seconds),
    getReady: ({ context }) => seconds(context.config.get_ready_seconds),
    photoSelectWarn: ({ context }) => seconds(context.config.photo_select_warn_seconds),
    photoSelectGrace: ({ context }) => seconds(context.config.photo_select_grace_seconds),
    filterSelectWarn: ({ context }) => seconds(context.config.filter_select_warn_seconds),
    filterSelectGrace: ({ context }) => seconds(context.config.filter_select_grace_seconds),
    finalPreviewTimeout: ({ context }) => seconds(context.config.final_preview_timeout_seconds),
    printingMock: ({ context }) => seconds(context.config.printing_mock_seconds),
    qrDownload: ({ context }) => seconds(context.config.qr_download_seconds),
    thankYou: ({ context }) => seconds(context.config.thank_you_seconds),
  },
}).createMachine({
  id: "kiosk",
  context: ({ input }) => ({ config: input.config, error: null, retryTarget: null }),
  initial: "idle",
  states: {
    idle: {
      entry: "resetSession",
      on: { START: "packageSelect" },
    },

    // --- before payment: any timeout goes straight back to idle ---
    packageSelect: {
      on: { SELECT_PACKAGE: "payment", RESET: "idle" },
      after: { packageTimeout: "idle" },
    },
    payment: {
      // mock: auto-confirm after the configured delay. Replace with a guard on
      // real payment status later; PAYMENT_CONFIRMED already wired.
      on: { PAYMENT_CONFIRMED: "getReady", RESET: "packageSelect" },
      after: { paymentMock: "getReady" },
    },

    // --- after payment: timeouts auto-advance with defaults, never back to idle ---
    getReady: {
      on: { START_CAPTURE: "capturing" },
      after: { getReady: "capturing" },
    },
    capturing: {
      entry: "clearError",
      invoke: {
        src: "captureSequence",
        onDone: "photoSelect",
        onError: { target: "error", actions: ["assignError", "markRetryCapture"] },
      },
      on: {
        CAPTURE_DONE: "photoSelect",
        CAPTURE_FAILED: { target: "error", actions: ["assignError", "markRetryCapture"] },
      },
    },

    photoSelect: {
      initial: "active",
      on: {
        NEXT: { target: "filterSelect", guard: "hasExactSelection" },
        RETAKE: "capturing",
        BACK: "capturing",
      },
      states: {
        active: { after: { photoSelectWarn: "warning" } },
        warning: {
          after: { photoSelectGrace: { target: "#kiosk.filterSelect", actions: "autoSelectPhotos" } },
        },
      },
    },

    filterSelect: {
      initial: "active",
      on: { NEXT: "frameSelect", BACK: "photoSelect" },
      states: {
        active: { after: { filterSelectWarn: "warning" } },
        warning: { after: { filterSelectGrace: "#kiosk.frameSelect" } },
      },
    },

    frameSelect: {
      initial: "active",
      on: { NEXT: "finalPreview", BACK: "filterSelect" },
      states: {
        active: { after: { filterSelectWarn: "warning" } },
        warning: {
          after: { filterSelectGrace: { target: "#kiosk.finalPreview", actions: "keepCurrentTemplate" } },
        },
      },
    },

    finalPreview: {
      on: { PRINT: "printing", EDIT: "filterSelect" },
      after: { finalPreviewTimeout: "printing" },
    },

    printing: {
      initial: "rendering",
      states: {
        rendering: {
          invoke: {
            src: "renderCollage",
            // spec: even if render/print fails, the guest must still reach the QR screen
            onDone: "settling",
            onError: { target: "settling", actions: "assignError" },
          },
        },
        settling: {
          after: { printingMock: "#kiosk.qrDownload" },
        },
      },
    },

    qrDownload: {
      on: { FINISH: "thankYou" },
      after: { qrDownload: "thankYou" },
    },

    thankYou: {
      after: { thankYou: "idle" },
    },

    error: {
      on: {
        RETRY: [
          { target: "capturing", guard: ({ context }) => context.retryTarget === "capturing" },
          { target: "idle" },
        ],
        RESET: "idle",
      },
      exit: "clearError",
    },
  },
});
