import { describe, expect, it } from "vitest";
import type { ToolCall } from "../api/client";
import { storyCalls } from "./storyCalls";

const call = (name: string, output: string, failed = false): ToolCall => ({ name, args: {}, output, failed });

describe("storyCalls", () => {
  it("keeps story-tool calls that produced text", () => {
    const story = call("Story Generator Tool", "Ana: Hola.");
    expect(storyCalls([call("Add Word Tool", "ok"), story])).toEqual([story]);
  });
  it("drops failed calls, empty output and the tool's own refusals", () => {
    expect(storyCalls([
      call("Story Generator Tool", "Ana: Hola.", true),
      call("Story Generator Tool", "   "),
      call("Story Generator Tool", "Stories are not available yet for Klingon."),
      call("Story Generator Tool", "I'm having trouble writing a story right now."),
    ])).toEqual([]);
  });
});
