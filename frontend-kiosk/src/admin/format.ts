const WEEKDAYS = ["Chủ Nhật", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy"];
const SHORT_WEEKDAYS = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"];

export function money(value: number): string {
  return `${new Intl.NumberFormat("vi-VN").format(value)}đ`;
}

/** 2430000 -> "2,4tr", 180000 -> "180k" for chart labels. */
export function shortMoney(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1).replace(".", ",").replace(",0", "")}tr`;
  if (value >= 1000) return `${Math.round(value / 1000)}k`;
  return String(value);
}

export function isoDay(date = new Date()): string {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

export function shiftDay(day: string, delta: number): string {
  const date = new Date(`${day}T12:00:00`);
  date.setDate(date.getDate() + delta);
  return isoDay(date);
}

export function longDate(day: string): string {
  const date = new Date(`${day}T12:00:00`);
  const dd = String(date.getDate()).padStart(2, "0");
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  return `${WEEKDAYS[date.getDay()]} · ${dd}/${mm}/${date.getFullYear()}`;
}

export function shortWeekday(day: string): string {
  return SHORT_WEEKDAYS[new Date(`${day}T12:00:00`).getDay()];
}

export function dayMonth(day: string): string {
  const date = new Date(`${day}T12:00:00`);
  return `${String(date.getDate()).padStart(2, "0")}/${String(date.getMonth() + 1).padStart(2, "0")}`;
}

/** "2026-10-08T14:52:10" -> "14:52". */
export function time(iso: string | null | undefined, seconds = false): string {
  if (!iso) return "";
  return iso.slice(11, seconds ? 19 : 16);
}

/** "PB123456" -> "PB·3456", the short code the kiosk shows to the guest. */
export function sessionCode(id: string | null | undefined): string {
  if (!id) return "—";
  return id.startsWith("PB") ? `PB·${id.slice(-4)}` : id;
}

export function bytes(value: number): string {
  if (value >= 1024 ** 3) return `${(value / 1024 ** 3).toFixed(1).replace(".", ",")} GB`;
  if (value >= 1024 ** 2) return `${(value / 1024 ** 2).toFixed(1).replace(".", ",")} MB`;
  if (value >= 1024) return `${Math.round(value / 1024)} KB`;
  return `${value} B`;
}

export function percentChange(current: number, previous: number): number | null {
  if (!previous) return null;
  return Math.round(((current - previous) / previous) * 100);
}
