import type { SessionRow } from "./api";

/** "Đã in" once printed, "Đang chụp" for a fresh unprinted session, else "Chưa in". */
export function sessionStatus(row: SessionRow): { label: string; kind: "ok" | "live" | "warn" } {
  if (row.printed_at) return { label: "Đã in", kind: "ok" };
  const ageMinutes = (Date.now() - new Date(row.created_at).getTime()) / 60000;
  if (ageMinutes < 15) return { label: "Đang chụp", kind: "live" };
  return { label: "Chưa in", kind: "warn" };
}
