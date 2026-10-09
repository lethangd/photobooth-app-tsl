/** Small shared state: nav badges (PIN failures, printer problems) and toast messages. */
import { reactive } from "vue";

import { KIOSK, getJson, token, type DayStats, type Overview } from "./api";
import { isoDay } from "./format";

export const summary = reactive({
  pinFailed: 0,
  printerIssue: false,
  printerSeverity: "ok" as string,
  online: true,
  loaded: false,
});

let timer = 0;

export async function refreshSummary(): Promise<void> {
  if (!token.value) return;
  try {
    const [stats, overview] = await Promise.all([
      getJson<DayStats>(`${KIOSK}/stats?day=${isoDay()}`),
      getJson<Overview>(`${KIOSK}/overview`),
    ]);
    summary.pinFailed = stats.pin_failed;
    const severity = overview.printer.kiosk_printer?.severity ?? "error";
    summary.printerSeverity = severity;
    summary.printerIssue = severity === "warning" || severity === "error";
    summary.online = true;
  } catch {
    summary.online = false;
  } finally {
    summary.loaded = true;
  }
}

export function startSummaryPolling(): void {
  window.clearInterval(timer);
  void refreshSummary();
  timer = window.setInterval(() => void refreshSummary(), 30000);
}

export const toast = reactive({ text: "", error: false, nonce: 0 });

export function notify(text: string, error = false): void {
  toast.text = text;
  toast.error = error;
  toast.nonce += 1;
  const nonce = toast.nonce;
  window.setTimeout(() => {
    if (toast.nonce === nonce) toast.text = "";
  }, 3200);
}

export function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
