import { describe, expect, it } from "vitest";
import { checkTyped } from "./typed";

describe("checkTyped", () => {
  it.each([
    ["water", "water", "right"],
    ["  Water. ", "water", "right"],
    ["thank   you", "thank you", "right"],
    ["Danke!", "Danke", "right"],
    ["¡hola!", "hola", "right"],
    ["ありがとう。", "ありがとう", "right"],
    ["cafe", "café", "accents"],
    ["manana", "mañana", "accents"],
    ["mañana", "manana", "accents"],
    ["agua", "aqua", "wrong"],
    ["", "water", "wrong"],
    ["   ", "water", "wrong"],
    ["wate", "water", "wrong"],
  ] as const)("%j against %j is %s", (typed, answer, expected) => expect(checkTyped(typed, answer)).toBe(expected));

  it("treats the same letters written in different Unicode forms as equal", () => {
    expect(checkTyped("café", "café")).toBe("right");
  });
});
