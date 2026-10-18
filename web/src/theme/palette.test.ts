import { describe, expect, it } from "vitest";
import { contrast, hexToHsv, hexToRgb, hsvToHex, luminance, mix, normalizeHex, rgbToHex } from "./color";
import { derivePalette, PRESETS, PRESET_IDS, validColors, type Colors } from "./palette";
import { readFileSync } from "node:fs";
import { join } from "node:path";

describe("colour maths", () => {
  it("normalises hex and rejects junk", () => {
    expect(normalizeHex("#ABC")).toBe("#aabbcc");
    expect(normalizeHex("12ab34")).toBe("#12ab34");
    for (const bad of ["", "#12", "#12345", "#gggggg", "red", "#1234567"]) expect(normalizeHex(bad), bad).toBeNull();
  });
  it("round-trips hex, RGB and HSV", () => {
    expect(rgbToHex(hexToRgb("#3a7bd5"))).toBe("#3a7bd5");
    for (const hex of ["#000000", "#ffffff", "#ff0000", "#00ff00", "#0000ff", "#3a7bd5", "#808080", "#c2410c"]) expect(hsvToHex(hexToHsv(hex)), hex).toBe(hex);
    expect(hexToHsv("#ff0000")).toEqual({ h: 0, s: 1, v: 1 });
    expect(hexToHsv("#0000ff").h).toBe(240);
  });
  it("matches known luminance and contrast values", () => {
    expect(luminance("#ffffff")).toBeCloseTo(1, 5);
    expect(luminance("#000000")).toBe(0);
    expect(contrast("#000000", "#ffffff")).toBeCloseTo(21, 5);
    expect(contrast("#ffffff", "#000000")).toBeCloseTo(21, 5);
    expect(contrast("#777777", "#ffffff")).toBeCloseTo(4.48, 1);
    expect(contrast("#123456", "#123456")).toBe(1);
  });
  it("mixes between two colours", () => {
    expect(mix("#000000", "#ffffff", 0.5)).toBe("#808080");
    expect(mix("#102030", "#ffffff", 0)).toBe("#102030");
    expect(mix("#102030", "#ffffff", 1)).toBe("#ffffff");
  });
});

function rand(seed: number) { let s = seed; return () => (s = (s * 1664525 + 1013904223) % 4294967296) / 4294967296; }
const randomColors = (r: () => number): Colors => {
  const c = () => rgbToHex([r() * 255, r() * 255, r() * 255]);
  return { page: c(), cards: c(), text: c(), borders: c(), accent: c() };
};

describe("derivePalette", () => {
  it("always keeps white button text readable on the accent, over many random picks", () => {
    const r = rand(1);
    for (let i = 0; i < 400; i++) {
      const p = derivePalette(randomColors(r));
      expect(contrast(p.vars["--color-brand-600"], "#ffffff")).toBeGreaterThanOrEqual(4.5);
    }
  });
  it("on a light base the accent also reads as link text on the page and the cards", () => {
    const r = rand(5);
    let light = 0;
    for (let i = 0; i < 400; i++) {
      const c = randomColors(r);
      const p = derivePalette(c);
      if (p.base !== "light") continue;
      light++;
      const a = p.vars["--color-brand-600"];
      // the loop stops at black, which reads on any light page
      expect(contrast(a, c.page) >= 4.5 || a === "#000000").toBe(true);
      expect(contrast(a, c.cards) >= 4.5 || a === "#000000").toBe(true);
    }
    expect(light).toBeGreaterThan(50);
  });
  it("says so when it had to darken the accent, and not otherwise", () => {
    const base = PRESETS.ocean.colors;
    expect(derivePalette({ ...base, accent: "#ffee00" }).accentDarkened).toBe(true);
    expect(derivePalette(base).accentDarkened).toBe(false);
  });
  it("keeps hints readable on page, cards and subtle fill whenever the text itself is clearly readable", () => {
    const r = rand(2);
    let checked = 0;
    for (let i = 0; i < 600; i++) {
      const c = randomColors(r);
      c.borders = mix(c.page, c.borders, 0.3);
      c.cards = mix(c.page, c.cards, 0.25);                                  // cards near the page, as in real themes
      c.text = contrast("#000000", c.page) >= contrast("#ffffff", c.page) ? mix("#000000", c.text, r() * 0.2) : mix("#ffffff", c.text, r() * 0.2);
      if (contrast(c.text, c.page) < 7 || contrast(c.text, c.cards) < 7) continue;
      const p = derivePalette(c);
      for (const bg of [c.page, c.cards, p.vars["--color-slate-100"]]) expect(contrast(p.vars["--color-slate-500"], bg)).toBeGreaterThanOrEqual(4.5);
      checked++;
    }
    expect(checked).toBeGreaterThan(30);
  });
  it("detects a dark base from the page colour", () => {
    expect(derivePalette(PRESETS.midnight.colors).base).toBe("dark");
    expect(derivePalette(PRESETS.ocean.colors).base).toBe("light");
  });
  it("is deterministic and sets every token the stylesheet's dark block sets", () => {
    const p = derivePalette(PRESETS.forest.colors);
    expect(derivePalette(PRESETS.forest.colors)).toEqual(p);
    const css = readFileSync(join(process.cwd(), "src/index.css"), "utf8");
    const dark = css.slice(css.indexOf(".dark {"), css.indexOf("}", css.indexOf(".dark {")));
    for (const name of dark.match(/--color-[a-z0-9-]+/g)!) expect(p.vars, name).toHaveProperty(name);
    for (const name of ["--color-brand-50", "--color-brand-100", "--color-brand-200", "--color-brand-500", "--color-brand-600", "--color-brand-700", "--color-brand-800", "--color-brand-900"]) expect(p.vars).toHaveProperty(name);
  });
  it("orders the text tones from the text colour toward the page", () => {
    const p = derivePalette(PRESETS.ocean.colors);
    const d = (k: string) => contrast(p.vars[k], PRESETS.ocean.colors.page);
    expect(d("--color-slate-900")).toBeGreaterThanOrEqual(d("--color-slate-800"));
    expect(d("--color-slate-800")).toBeGreaterThanOrEqual(d("--color-slate-700"));
    expect(d("--color-slate-700")).toBeGreaterThanOrEqual(d("--color-slate-600"));
    expect(d("--color-slate-600")).toBeGreaterThanOrEqual(d("--color-slate-500"));
  });
});

describe("presets", () => {
  it.each(PRESET_IDS)("%s is readable: text 7:1 on page and cards, hints 4.5:1, button text 4.5:1, accent not darkened", (id) => {
    const c = PRESETS[id].colors;
    const p = derivePalette(c);
    expect(contrast(c.text, c.page)).toBeGreaterThanOrEqual(7);
    expect(contrast(c.text, c.cards)).toBeGreaterThanOrEqual(7);
    for (const bg of [c.page, c.cards, p.vars["--color-slate-100"]]) expect(contrast(p.vars["--color-slate-500"], bg)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(p.vars["--color-brand-600"], "#ffffff")).toBeGreaterThanOrEqual(4.5);
    expect(p.accentDarkened).toBe(false);
    expect(p.vars["--color-brand-600"]).toBe(c.accent);
  });
  it("the sample custom palettes (very light, very dark, saturated) stay usable", () => {
    for (const c of [
      { page: "#ffffff", cards: "#fafafa", text: "#111111", borders: "#dddddd", accent: "#ffd400" },
      { page: "#000000", cards: "#0a0a0a", text: "#ffffff", borders: "#333333", accent: "#00ffaa" },
      { page: "#ff0000", cards: "#00ff00", text: "#0000ff", borders: "#ffff00", accent: "#ff00ff" },
    ]) {
      const p = derivePalette(c);
      expect(contrast(p.vars["--color-brand-600"], "#ffffff")).toBeGreaterThanOrEqual(4.5);
      for (const v of Object.values(p.vars)) expect(v).toMatch(/^#[0-9a-f]{6}$/);
    }
  });
});

describe("validColors", () => {
  it("accepts five valid colours and ignores anything else", () => {
    expect(validColors({ page: "#FFF", cards: "#ffffff", text: "#000", borders: "#ccc", accent: "#00f" })).toEqual({ page: "#ffffff", cards: "#ffffff", text: "#000000", borders: "#cccccc", accent: "#0000ff" });
    expect(validColors({ page: "#fff" })).toBeNull();
    expect(validColors({ page: "x", cards: "#fff", text: "#fff", borders: "#fff", accent: "#fff" })).toBeNull();
    expect(validColors(null)).toBeNull();
  });
});
