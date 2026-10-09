/**
 * Sticker packs of the decorate screen (06b). Vector stickers are 100×100 SVGs drawn the same way on
 * screen and into the print overlay; chips are text pills drawn with the kiosk fonts.
 */

export type StickerDef =
  | { id: string; kind: "svg"; svg: string; label: string }
  | { id: string; kind: "chip"; text: string; bg: string; ink: string; label: string };

export interface StickerPack {
  id: string;
  name: string;
  items: StickerDef[];
}

const HOLO = "holo";

function svg(body: string, defs = ""): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs>${defs}</defs>${body}</svg>`;
}

const STAR4 = "M50 0C54 33 67 46 100 50C67 54 54 67 50 100C46 67 33 54 0 50C33 46 46 33 50 0Z";
const HEART =
  "M50 88C20 66 6 50 6 32C6 18 17 8 30 8C40 8 46 14 50 22C54 14 60 8 70 8C83 8 94 18 94 32C94 50 80 66 50 88Z";
const CHROME_GRADIENT =
  '<radialGradient id="c" cx="32%" cy="28%" r="75%"><stop offset="0" stop-color="#fff"/><stop offset=".3" stop-color="#DDE1E8"/><stop offset=".72" stop-color="#A3ABBA"/><stop offset="1" stop-color="#EEF0F4"/></radialGradient>';

const star = (color: string) => svg(`<path d="${STAR4}" fill="${color}"/>`);
const heart = (color: string) => svg(`<path d="${HEART}" fill="${color}"/>`);
const chip = (id: string, text: string, bg: string, ink = "#14161C"): StickerDef => ({
  id,
  kind: "chip",
  text,
  bg,
  ink,
  label: text,
});
const art = (id: string, label: string, body: string): StickerDef => ({ id, kind: "svg", svg: body, label });

const SPHERE = svg('<circle cx="50" cy="50" r="46" fill="url(#c)"/>', CHROME_GRADIENT);
const CAPSULE = svg(
  '<rect x="6" y="30" width="88" height="40" rx="20" fill="#2B3BFF" transform="rotate(-18 50 50)"/>',
);
const SMILEY = svg(
  '<circle cx="50" cy="50" r="44" fill="#FFE14D"/><circle cx="36" cy="40" r="6" fill="#14161C"/><circle cx="64" cy="40" r="6" fill="#14161C"/><path d="M30 58Q50 80 70 58" stroke="#14161C" stroke-width="7" fill="none" stroke-linecap="round"/>',
);
const SPARKLES = svg(
  `<path d="${STAR4}" fill="#C9B8FF" transform="translate(4 4) scale(.62)"/><path d="${STAR4}" fill="#A8F0E0" transform="translate(58 52) scale(.4)"/><path d="${STAR4}" fill="#FFD2B8" transform="translate(60 8) scale(.3)"/>`,
);
const FLOWER = svg(
  '<g fill="#C9B8FF"><circle cx="50" cy="22" r="20"/><circle cx="78" cy="42" r="20"/><circle cx="67" cy="74" r="20"/><circle cx="33" cy="74" r="20"/><circle cx="22" cy="42" r="20"/></g><circle cx="50" cy="50" r="15" fill="#FFE14D"/>',
);
const BOLT = svg('<path d="M58 4L18 56h26l-8 40 46-56H54z" fill="#2B3BFF"/>');

const MAPLE = svg(
  '<path d="M50 4l9 20 15-8-4 22 22-4-10 16 14 8-26 8 4 14-20-8v24h-8V72l-20 8 4-14-26-8 14-8-10-16 22 4-4-22 15 8z" fill="#E8692E"/>',
);
const LEAF = svg(
  '<path d="M14 86C10 40 40 10 90 10 90 60 60 90 14 86z" fill="#F2B53A"/><path d="M14 86L70 30" stroke="#B9791C" stroke-width="5"/>',
);
const ACORN = svg(
  '<path d="M22 42h56c0 30-12 50-28 54-16-4-28-24-28-54z" fill="#C98545"/><path d="M16 44c0-18 16-28 34-28s34 10 34 28z" fill="#7A4A22"/><rect x="47" y="4" width="6" height="14" rx="3" fill="#7A4A22"/>',
);
const MUSHROOM = svg(
  '<rect x="38" y="50" width="24" height="40" rx="10" fill="#F5E6D3"/><path d="M8 54C8 26 28 10 50 10s42 16 42 44z" fill="#E5263A"/><circle cx="32" cy="34" r="7" fill="#fff"/><circle cx="62" cy="26" r="6" fill="#fff"/><circle cx="72" cy="44" r="5" fill="#fff"/>',
);
const COFFEE = svg(
  '<path d="M18 36h56l-6 52H24z" fill="#FFFFFF" stroke="#14161C" stroke-width="5"/><path d="M74 46h8a10 10 0 0 1 0 20h-10" fill="none" stroke="#14161C" stroke-width="5"/><path d="M36 8c-6 8 6 12 0 20M54 8c-6 8 6 12 0 20" stroke="#B9791C" stroke-width="5" fill="none" stroke-linecap="round"/>',
);

const PUMPKIN = svg(
  '<ellipse cx="32" cy="58" rx="22" ry="32" fill="#F07A1A"/><ellipse cx="68" cy="58" rx="22" ry="32" fill="#F07A1A"/><ellipse cx="50" cy="58" rx="22" ry="34" fill="#FF9433"/><rect x="45" y="12" width="10" height="16" rx="4" fill="#3E7B27"/><path d="M34 50l8 8h-16zM66 50l8 8h-16z" fill="#14161C"/><path d="M34 72q16 12 32 0" stroke="#14161C" stroke-width="5" fill="none"/>',
);
const GHOST = svg(
  '<path d="M18 92V42C18 22 32 8 50 8s32 14 32 34v50l-10-8-11 8-11-8-11 8-11-8z" fill="#FFFFFF" stroke="#14161C" stroke-width="4"/><ellipse cx="38" cy="42" rx="6" ry="9" fill="#14161C"/><ellipse cx="62" cy="42" rx="6" ry="9" fill="#14161C"/>',
);
const BAT = svg(
  '<path d="M50 40c-6-10-14-14-26-12 6 4 6 10 2 14-8-4-16-2-22 6 10-2 16 2 18 10 8-6 18-6 28 4 10-10 20-10 28-4 2-8 8-12 18-10-6-8-14-10-22-6-4-4-4-10 2-14-12-2-20 2-26 12z" fill="#14161C"/>',
);
const CANDY = svg(
  '<circle cx="50" cy="50" r="22" fill="#C9B8FF"/><path d="M28 50L6 36v28zM72 50l22-14v28z" fill="#A8F0E0"/><path d="M38 38l24 24M50 30l18 18M30 50l18 18" stroke="#fff" stroke-width="5"/>',
);

const LANTERN_STAR = svg(
  '<path d="M50 6l12 30 32 2-25 20 9 32-28-18-28 18 9-32L6 38l32-2z" fill="#E5263A" stroke="#FFD24D" stroke-width="4" stroke-linejoin="round"/><circle cx="50" cy="50" r="8" fill="#FFD24D"/>',
);
const MOON = svg('<path d="M64 8a42 42 0 1 0 28 66A36 36 0 0 1 64 8z" fill="#FFD24D"/>');
const MOONCAKE = svg(
  '<circle cx="50" cy="50" r="42" fill="#D9933D"/><circle cx="50" cy="50" r="30" fill="none" stroke="#B5701F" stroke-width="5"/><path d="M50 30v40M30 50h40" stroke="#B5701F" stroke-width="5" stroke-linecap="round"/>',
);
const LANTERN = svg(
  '<rect x="44" y="4" width="12" height="10" rx="3" fill="#C29B2A"/><ellipse cx="50" cy="50" rx="34" ry="36" fill="#E5263A"/><path d="M50 14v72M30 18q-10 32 0 64M70 18q10 32 0 64" stroke="#FFB3A0" stroke-width="3" fill="none"/><path d="M44 86h12l-2 10h-8z" fill="#C29B2A"/>',
);

const DOUBLE_HEART = svg(
  `<path d="${HEART}" fill="#FF6B8A" transform="translate(-4 8) scale(.7)"/><path d="${HEART}" fill="#E5263A" transform="translate(34 30) scale(.62)"/>`,
);
const LETTER = svg(
  `<rect x="8" y="22" width="84" height="58" rx="8" fill="#FFFFFF" stroke="#14161C" stroke-width="4"/><path d="M10 26l40 30 40-30" stroke="#14161C" stroke-width="4" fill="none"/><path d="${HEART}" fill="#E5263A" transform="translate(38 46) scale(.24)"/>`,
);
const ARROW_HEART = svg(
  `<path d="${HEART}" fill="#FF6B8A" transform="translate(14 14) scale(.72)"/><path d="M8 84L92 16" stroke="#14161C" stroke-width="5"/><path d="M92 16l-14 2 12 12z" fill="#14161C"/>`,
);

export const STICKER_PACKS: StickerPack[] = [
  {
    id: "y2k",
    name: "Y2K",
    items: [
      art("y-star", "Ngôi sao xanh", star("#2B3BFF")),
      art("y-star2", "Ngôi sao tím", star("#C9B8FF")),
      art("y-sphere", "Cầu chrome", SPHERE),
      chip("y-bff", "BFF", HOLO),
      chip("y-omg", "OMG", "#A8F0E0"),
      art("y-sparkles", "Lấp lánh", SPARKLES),
      chip("y-xoxo", "xoxo", "#FFD2B8"),
      chip("y-y2k", "Y2K", "#DCE0FF"),
      art("y-capsule", "Viên nang", CAPSULE),
      chip("y-2026", "2026", "#2B3BFF", "#FFFFFF"),
      art("y-smile", "Mặt cười", SMILEY),
      art("y-flower", "Bông hoa", FLOWER),
      art("y-bolt", "Tia chớp", BOLT),
      art("y-heart", "Trái tim", heart("#2B3BFF")),
      chip("y-slay", "SLAY", "#14161C", "#FFFFFF"),
    ],
  },
  {
    id: "autumn",
    name: "Mùa thu",
    items: [
      art("a-maple", "Lá phong", MAPLE),
      art("a-leaf", "Lá vàng", LEAF),
      art("a-acorn", "Hạt dẻ", ACORN),
      art("a-mushroom", "Cây nấm", MUSHROOM),
      art("a-coffee", "Cà phê", COFFEE),
      chip("a-thu", "Thu ơi", "#F2B53A"),
      chip("a-cozy", "cozy", "#FFD2B8"),
      art("a-star", "Ngôi sao cam", star("#E8692E")),
    ],
  },
  {
    id: "halloween",
    name: "Halloween",
    items: [
      art("h-pumpkin", "Bí ngô", PUMPKIN),
      art("h-ghost", "Con ma", GHOST),
      art("h-bat", "Con dơi", BAT),
      art("h-candy", "Kẹo", CANDY),
      chip("h-boo", "BOO!", "#14161C", "#FF9433"),
      chip("h-trick", "Trick or treat", "#FF9433"),
      art("h-moon", "Trăng", MOON),
      art("h-star", "Ngôi sao tím", star("#9B7BFF")),
    ],
  },
  {
    id: "midautumn",
    name: "Trung thu",
    items: [
      art("m-star", "Đèn ông sao", LANTERN_STAR),
      art("m-moon", "Trăng rằm", MOON),
      art("m-cake", "Bánh trung thu", MOONCAKE),
      art("m-lantern", "Đèn lồng", LANTERN),
      chip("m-tt", "Trung thu", "#E5263A", "#FFD24D"),
      chip("m-ram", "Rằm tháng 8", "#FFD24D"),
      art("m-sparkles", "Lấp lánh", SPARKLES),
    ],
  },
  {
    id: "valentine",
    name: "Valentine",
    items: [
      art("v-heart", "Trái tim", heart("#E5263A")),
      art("v-hearts", "Hai trái tim", DOUBLE_HEART),
      art("v-letter", "Thư tình", LETTER),
      art("v-arrow", "Mũi tên tình yêu", ARROW_HEART),
      chip("v-love", "LOVE", "#FF6B8A", "#FFFFFF"),
      chip("v-xoxo", "xoxo", "#FFD2DC"),
      art("v-pink", "Tim hồng", heart("#FF6B8A")),
      art("v-star", "Ngôi sao hồng", star("#FF6B8A")),
    ],
  },
];

/** Styles for free text typed by the guest. */
export const TEXT_STYLES: { id: string; bg: string; ink: string; label: string }[] = [
  { id: "holo", bg: HOLO, ink: "#14161C", label: "Holo" },
  { id: "cobalt", bg: "#2B3BFF", ink: "#FFFFFF", label: "Cobalt" },
  { id: "white", bg: "#FFFFFF", ink: "#14161C", label: "Trắng" },
  { id: "ink", bg: "#14161C", ink: "#FFFFFF", label: "Đen" },
  { id: "none", bg: "transparent", ink: "#FFFFFF", label: "Chữ trắng" },
];

export const PEN_COLORS = ["#2B3BFF", "#14161C", "#FFFFFF", "#C9B8FF", "#A8F0E0", "#FFD2B8", "#E5263A"];

export function svgUrl(markup: string): string {
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(markup)}`;
}

/** CSS background for a chip (the holo pill is a gradient). */
export function chipBackground(bg: string): string {
  return bg === HOLO ? "linear-gradient(90deg, #c9b8ff, #a8f0e0, #ffd2b8)" : bg;
}

export function isHolo(bg: string): boolean {
  return bg === HOLO;
}
