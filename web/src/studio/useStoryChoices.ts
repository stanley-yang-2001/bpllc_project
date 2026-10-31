import { useState } from "react";
import type { StoryOptions } from "../api/client";
import { nothingTicked, setIdsToSend, type SetChoice } from "../components/SetPicker";
import { CLASSIC, CUSTOM, CUSTOM_TOPIC, customLabel } from "./labels";
import { useDifficulty } from "./useDifficulty";

/** Everything the learner picks before Make: the kind, the topic, the difficulty and the sets, and the request that makes. */
export function useStoryChoices(language: string, options: StoryOptions | undefined) {
  const [type, setType] = useState("");
  const [topic, setTopic] = useState("");
  const [custom, setCustom] = useState("");
  const [customTopic, setCustomTopic] = useState("");
  const [sets, setSets] = useState<SetChoice>(null);       // null = every set (General always among them)
  const difficulty = useDifficulty(options?.difficulty);

  const kind = type === CUSTOM ? customLabel(custom) ?? "" : type;       // "" = surprise me (or an unusable label, which blocks Make)
  const customBad = type === CUSTOM && !kind;
  const topicValue = topic === CUSTOM_TOPIC ? customLabel(customTopic) ?? "" : topic;    // same rule and limits as a custom kind
  const topicOn = !!kind && !CLASSIC.includes(kind);
  const topicBad = topicOn && topic === CUSTOM_TOPIC && !topicValue;
  const request = {
    language, story_type: kind || undefined, topic: !topicOn ? undefined : topicValue || undefined, ...difficulty.choice,
    ...(setIdsToSend(sets) ? { set_ids: setIdsToSend(sets) } : {}),
  };
  return {
    type, setType, topic, setTopic, custom, setCustom, customTopic, setCustomTopic, sets, setSets, difficulty,
    kind, customBad, topicOn, topicBad, request, canMake: !(customBad || topicBad || difficulty.bad || nothingTicked(sets)),
  };
}
export type StoryChoices = ReturnType<typeof useStoryChoices>;
