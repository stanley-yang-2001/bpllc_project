import type { ToolCall } from "../api/client";

const STORY_TOOL = "Story Generator Tool";
const NOT_A_STORY = /not available yet|having trouble/i;          // the tool's own refusal messages

/** The story-tool calls of one reply that produced a story the learner can keep (not a failure and not one of the tool's refusals). */
export const storyCalls = (calls: ToolCall[]): ToolCall[] =>
  calls.filter((c) => c.name === STORY_TOOL && !c.failed && c.output.trim() !== "" && !NOT_A_STORY.test(c.output));
