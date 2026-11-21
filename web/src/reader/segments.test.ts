import { describe, expect, it } from "vitest";
import { learnable, segments } from "./segments";

const joined = (parts: { text: string }[]) => parts.map((p) => p.text).join("");

describe("segments", () => {
  it("cuts a story into the learner's words, the other words and what lies between, and the pieces rejoin to the text", () => {
    const text = "The dogs were running.\nBen: A dog!";
    const parts = segments(text, [{ start: 4, end: 8, word_id: 1 }, { start: 14, end: 21, word_id: 2 }], "en");
    expect(joined(parts)).toBe(text);
    expect(parts.filter((p) => p.kind === "known").map((p) => [p.text, "wordId" in p ? p.wordId : 0])).toEqual([["dogs", 1], ["running", 2]]);
    expect(parts.filter((p) => p.kind === "other").map((p) => p.text)).toEqual(["The", "were", "Ben", "A", "dog"]);
    expect(parts.every((p) => text.slice(p.start, p.end) === p.text)).toBe(true);
  });

  it("makes every word tappable when the learner has none of them, and leaves numbers and punctuation alone", () => {
    const parts = segments("Room 12, please!", [], "en");
    expect(parts.filter((p) => p.kind === "other").map((p) => p.text)).toEqual(["Room", "please"]);
    expect(joined(parts)).toBe("Room 12, please!");
  });

  it("keeps an apostrophe word whole", () => {
    expect(segments("Don't stop.", [], "en").filter((p) => p.kind === "other").map((p) => p.text)).toEqual(["Don't", "stop"]);
  });

  it("finds the words of a language written without spaces", () => {
    const text = "私は毎日りんごを食べます。";
    const parts = segments(text, [], "ja");
    expect(joined(parts)).toBe(text);
    const words = parts.filter((p) => p.kind === "other").map((p) => p.text);
    expect(words.length).toBeGreaterThan(2);                      // cut into words, not one long piece (needs the browser's word splitter, which Node has)
    expect(words.join("")).toBe("私は毎日りんごを食べます");
  });

  it("ignores a span that overlaps another or leaves the text instead of trusting it", () => {
    const text = "one two three";
    const parts = segments(text, [{ start: 0, end: 3, word_id: 1 }, { start: 2, end: 5, word_id: 2 }, { start: 8, end: 99, word_id: 3 }], "en");
    expect(parts.filter((p) => p.kind === "known").map((p) => p.text)).toEqual(["one"]);
    expect(joined(parts)).toBe(text);
  });

  it("reads positions as JavaScript does, after an emoji", () => {
    const text = "😀 The dog ran.";
    const parts = segments(text, [{ start: 7, end: 10, word_id: 1 }], "en");
    expect(parts.find((p) => p.kind === "known")?.text).toBe("dog");
    expect(joined(parts)).toBe(text);
  });
});

describe("learnable: the form to add for a tapped word", () => {
  const at = (text: string, word: string, nth = 0) => {
    let i = -1;
    for (let k = 0; k <= nth; k++) i = text.indexOf(word, i + 1);
    return learnable(text, i, i + word.length, "en");
  };
  it("lowers a capital that is there only because the word starts a sentence", () => {
    expect(at("The dog ran. Then it slept.", "The")).toBe("the");
    expect(at("The dog ran. Then it slept.", "Then")).toBe("then");
    expect(at("Ana: Hello there.\nBen: Hi.", "Hello")).toBe("hello");
    expect(at("She said: “Good morning.”", "Good")).toBe("good");
    expect(at("A line\nBen waits.", "Ben")).toBe("ben");
  });
  it("keeps a capital in the middle of a sentence, a capital word and the German capitals", () => {
    expect(at("She met Ana today.", "Ana")).toBe("Ana");
    expect(at("It is NASA.", "NASA")).toBe("NASA");
    expect(learnable("Das Haus ist groß.", 0, 3, "de")).toBe("Das");
    const de = "Ich sehe das Haus.";
    expect(learnable(de, de.indexOf("Haus"), de.indexOf("Haus") + 4, "de")).toBe("Haus");
  });
  it("leaves a language without capitals as written", () => {
    expect(learnable("我喜欢苹果。", 3, 5, "zh")).toBe("苹果");
  });
});
