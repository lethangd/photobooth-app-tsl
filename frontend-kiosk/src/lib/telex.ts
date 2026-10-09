/**
 * Minimal Telex typing for the on-screen keyboard: aa→â, aw→ă, ee→ê, oo→ô, ow→ơ, uw→ư, dd→đ,
 * and the tone keys s (sắc), f (huyền), r (hỏi), x (ngã), j (nặng), z (remove). Typing the same
 * modifier twice undoes it (e.g. "ass" → "as"), like the usual Vietnamese keyboards.
 */

const TONED: Record<string, string> = {
  a: "aáàảãạ",
  ă: "ăắằẳẵặ",
  â: "âấầẩẫậ",
  e: "eéèẻẽẹ",
  ê: "êếềểễệ",
  i: "iíìỉĩị",
  o: "oóòỏõọ",
  ô: "ôốồổỗộ",
  ơ: "ơớờởỡợ",
  u: "uúùủũụ",
  ư: "ưứừửữự",
  y: "yýỳỷỹỵ",
};
const TONE_KEYS: Record<string, number> = { s: 1, f: 2, r: 3, x: 4, j: 5, z: 0 };
const HATS: Record<string, string> = { a: "â", e: "ê", o: "ô" };
const HORNS: Record<string, string> = { a: "ă", o: "ơ", u: "ư" };
const MARKED = new Set(["ă", "â", "ê", "ô", "ơ", "ư"]);

const DECOMPOSE = new Map<string, [string, number]>();
for (const [base, row] of Object.entries(TONED))
  [...row].forEach((ch, tone) => DECOMPOSE.set(ch, [base, tone]));

function split(ch: string): [string, number] {
  return DECOMPOSE.get(ch) ?? [ch, 0];
}

function isVowel(ch: string): boolean {
  return DECOMPOSE.has(ch);
}

/** Indices of the vowels that carry the tone ("qu" and "gi" + vowel start with a consonant). */
function vowelIndices(chars: string[]): number[] {
  const bases = chars.map((ch) => split(ch)[0]);
  const indices: number[] = [];
  bases.forEach((base, i) => {
    if (!isVowel(chars[i])) return;
    if (i === 1 && base === "u" && bases[0] === "q") return;
    if (i === 1 && base === "i" && bases[0] === "g" && bases.length > 2 && isVowel(chars[2])) return;
    indices.push(i);
  });
  return indices;
}

function toneTarget(chars: string[]): number {
  const vowels = vowelIndices(chars);
  if (!vowels.length) return -1;
  const bases = chars.map((ch) => split(ch)[0]);
  const marked = vowels.filter((i) => MARKED.has(bases[i]));
  if (marked.length) return marked[marked.length - 1];
  if (vowels.length === 1) return vowels[0];
  const last = vowels[vowels.length - 1];
  const endsWithVowel = last === chars.length - 1;
  if (!endsWithVowel) return last;
  const pair = bases[vowels[0]] + bases[vowels[1]];
  if (vowels.length === 2) return ["oa", "oe", "uy"].includes(pair) ? vowels[1] : vowels[0];
  return vowels[1];
}

/** Word with ``tone`` placed on the right vowel (and removed from every other one). */
function placeTone(chars: string[], tone: number): string[] {
  const plain = chars.map((ch) => split(ch)[0]);
  const target = toneTarget(plain);
  if (target >= 0 && tone) plain[target] = TONED[plain[target]][tone];
  return plain;
}

function currentTone(chars: string[]): number {
  for (const ch of chars) {
    const [, tone] = split(ch);
    if (tone) return tone;
  }
  return 0;
}

/** ``text`` after typing ``key`` with Telex rules applied to the last word. */
export function typeTelex(text: string, key: string): string {
  const lowerKey = key.toLowerCase();
  const cut = text.search(/[^\s]*$/);
  const head = text.slice(0, cut);
  const word = text.slice(cut);
  const upper = [...word].map((ch) => ch !== ch.toLowerCase());
  const chars = [...word.toLowerCase()];
  const tone = currentTone(chars);
  const restore = (result: string[], extra = ""): string =>
    head + result.map((ch, i) => (upper[i] ? ch.toUpperCase() : ch)).join("") + extra;

  if (lowerKey in TONE_KEYS && vowelIndices(chars.map((ch) => split(ch)[0])).length) {
    const next = TONE_KEYS[lowerKey];
    if (next === 0) return restore(placeTone(chars, 0));
    if (next === tone) return restore(placeTone(chars, 0), key); // "ass" → "as"
    return restore(placeTone(chars, next));
  }

  if (lowerKey in HATS) {
    for (let i = chars.length - 1; i >= 0; i -= 1) {
      const [base, t] = split(chars[i]);
      if (base === lowerKey || base === HATS[lowerKey]) {
        const swapped = base === lowerKey ? HATS[lowerKey] : lowerKey;
        chars[i] = TONED[swapped][t];
        return restore(placeTone(chars, tone), base === lowerKey ? "" : key);
      }
      if (isVowel(chars[i]) && i < chars.length - 1) break;
    }
  }

  if (lowerKey === "d" && (chars[0] === "d" || chars[0] === "đ")) {
    const toStroke = chars[0] === "d";
    chars[0] = toStroke ? "đ" : "d";
    return restore(chars, toStroke ? "" : key);
  }

  if (lowerKey === "w") {
    const bases = chars.map((ch) => split(ch)[0]);
    const uo = bases.join("").lastIndexOf("uo");
    if (uo >= 0) {
      chars[uo] = TONED["ư"][split(chars[uo])[1]];
      chars[uo + 1] = TONED["ơ"][split(chars[uo + 1])[1]];
      return restore(placeTone(chars, tone));
    }
    for (let i = chars.length - 1; i >= 0; i -= 1) {
      const [base, t] = split(chars[i]);
      if (base in HORNS) {
        chars[i] = TONED[HORNS[base]][t];
        return restore(placeTone(chars, tone));
      }
      if (Object.values(HORNS).includes(base)) {
        const plain = Object.keys(HORNS).find((k) => HORNS[k] === base) as string;
        chars[i] = TONED[plain][t];
        return restore(placeTone(chars, tone), key);
      }
    }
  }

  const appended = [...chars, lowerKey];
  upper.push(key !== lowerKey);
  return (
    head +
    (tone && isVowel(lowerKey) ? placeTone(appended, tone) : appended)
      .map((ch, i) => (upper[i] ? ch.toUpperCase() : ch))
      .join("")
  );
}
