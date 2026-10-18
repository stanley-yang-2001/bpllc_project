import { describe, expect, it } from "vitest";
import { ApiError } from "../api/client";
import { errorMessage, htmlLang, translate, translateCount } from "./I18nProvider";
import { LOCALES, MESSAGES } from "./messages";

const rows = Object.entries(MESSAGES) as [string, readonly string[]][];
const holes = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",");

describe("message catalog", () => {
  it("has nine non-empty entries per message, in the fixed locale order", () => {
    expect(LOCALES).toEqual(["en", "es", "fr", "de", "it", "pt", "ja", "zh", "ko"]);
    for (const [key, row] of rows) {
      expect(row, key).toHaveLength(9);
      for (const s of row) expect(s.trim(), key).not.toBe("");
    }
  });
  it("uses the same {placeholders} in every language of a message", () => {
    for (const [key, row] of rows) for (const s of row) expect(holes(s), key).toBe(holes(row[0]));
  });
  it("has a .one and a .other for every plural", () => {
    for (const [key] of rows) {
      if (key.endsWith(".one")) expect(key.replace(/\.one$/, ".other") in MESSAGES, key).toBe(true);
      if (key.endsWith(".other")) expect(key.replace(/\.other$/, ".one") in MESSAGES, key).toBe(true);
    }
  });
  it("translates only the strings that should differ: no other language is a copy of English by accident", () => {
    // Allowed to match English: names and numbers-only rows that are the same word in that language.
    const copies = rows.filter(([, r]) => r.slice(1).every((s) => s === r[0]));
    expect(copies.map(([k]) => k)).toEqual([]);
  });
});

describe("translate", () => {
  it("fills placeholders, falls back to English for an unknown locale slot, and to the key for an unknown key", () => {
    expect(translate("es", "chat.thinking")).toBe("El tutor está pensando…");
    expect(translate("en", "tool.used", { name: "add_word" })).toBe("Used add_word");
    expect(translate("ja", "tool.used", { name: "x" })).toBe("xを使用");
    expect(translate("en", "no.such.key")).toBe("no.such.key");
    expect(translate("en", "tool.used")).toBe("Used {name}");
  });
  it("picks the plural form by the locale's rules", () => {
    expect(translateCount("en", "report.outside", 1, { words: "a" })).toBe("1 word outside your list: a.");
    expect(translateCount("en", "report.outside", 3, { words: "a, b, c" })).toBe("3 words outside your list: a, b, c.");
    expect(translateCount("fr", "report.outside", 0, { words: "" })).toContain("0 mot");
    expect(translateCount("ja", "report.outside", 2, { words: "x" })).toBe("リストにない単語が2語：x。");
  });
  it("maps the html lang attribute, Chinese as Simplified", () => {
    expect(htmlLang("zh")).toBe("zh-Hans");
    expect(htmlLang("ko")).toBe("ko");
  });
});

describe("errorMessage", () => {
  it("translates a known error code, shows an unknown server message as written, and falls back otherwise", () => {
    expect(errorMessage("de", new ApiError(429, "tutor_busy", "Busy"))).toBe(translate("de", "error.tutor_busy"));
    expect(errorMessage("de", new ApiError(422, "validation_error", "Name is too long"))).toBe("Name is too long");
    expect(errorMessage("es", new Error("boom"))).toBe(translate("es", "error.generic"));
  });
});
