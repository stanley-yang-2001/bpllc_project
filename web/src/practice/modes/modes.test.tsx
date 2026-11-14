import { describe, expect, it } from "vitest";
import { MODE_ORDER, MODES } from ".";

describe("practice mode registry", () => {
  it("lists every mode once, in menu order, each with a menu card and a session", () => {
    expect(MODE_ORDER).toEqual(["choice", "cards", "pos", "dictation", "cloze"]);
    for (const id of MODE_ORDER) {
      expect(typeof MODES[id].Tile).toBe("function");
      expect(typeof MODES[id].Session).toBe("function");
    }
  });
});
