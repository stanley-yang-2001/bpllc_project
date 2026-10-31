import { useState } from "react";
import type { DifficultyChoice, StoryOptions } from "../api/client";

export type Tier = "" | "easy" | "medium" | "hard" | "custom";
type Key = "length" | "own_words" | "uncommon_pct";
export type DifficultyOptions = StoryOptions["difficulty"];

const whole = (text: string, bounds: number[] | undefined): number | null => {
  const n = Number(text);
  return bounds && text.trim() !== "" && Number.isInteger(n) && n >= bounds[0] && n <= bounds[1] ? n : null;
};

/** The learner's difficulty choice. The preset sizes and the limits come from the API (tutor_core is where they are written),
 * so they are not copied here. Until they arrive a custom number is not accepted. */
export function useDifficulty(options: DifficultyOptions | undefined) {
  const [tier, setTier] = useState<Tier>("");
  const [nums, setNums] = useState({ length: "110", own_words: "5", uncommon_pct: "10" });
  const limits = options?.limits;
  const picked: Record<Key, number | null> = {
    length: whole(nums.length, limits?.length), own_words: whole(nums.own_words, limits?.own_words), uncommon_pct: whole(nums.uncommon_pct, limits?.uncommon_pct),
  };
  const bad = tier === "custom" && (picked.length === null || picked.own_words === null || picked.uncommon_pct === null);
  const choice: DifficultyChoice = tier === "" ? {} : tier === "custom"
    ? { difficulty: "custom", length: picked.length ?? undefined, own_words: picked.own_words ?? undefined, uncommon_pct: picked.uncommon_pct ?? undefined }
    : { difficulty: tier };
  return { tier, setTier, nums, setNums, picked, bad, choice, options };
}
export type Difficulty = ReturnType<typeof useDifficulty>;
