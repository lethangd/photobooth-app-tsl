import { describe, expect, it } from "vitest";

import { typeTelex } from "./telex";

function type(keys: string): string {
  return [...keys].reduce((text, key) => typeTelex(text, key), "");
}

describe("telex", () => {
  it.each([
    ["Hooij banj thaan", "Hội bạn thân"],
    ["ddepj quas", "đẹp quá"],
    ["ddeepj", "đệp"],
    ["nhuwngx", "những"],
    ["tuowngf", "tường"],
    ["Trung thu", "Trung thu"],
    ["hoaf", "hoà"],
    ["mais mais", "mái mái"],
    ["giaf", "già"],
    ["quas", "quá"],
    ["ass", "as"],
    ["BFF 2026", "BFF 2026"],
    ["Vieejt Nam", "Việt Nam"],
  ])("%s → %s", (keys, expected) => {
    expect(type(keys)).toBe(expected);
  });
});
