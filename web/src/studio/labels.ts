import type { DifficultyChoice, GeneratedStory } from "../api/client";

export const CLASSIC = ["narration", "dialogue"];          // these two have no topic
export const CUSTOM = "__custom__";                        // the "Write my own…" choice; never sent to the API
export const CUSTOM_TOPIC = "__custom_topic__";            // the same for the topic
export const CUSTOM_MAX = 40;

/** The same rule the API applies (tutor_core.prompts.clean_free_text), so a bad label is explained here and Make stays off.
 * The API is the authority and checks again. */
export function customLabel(text: string): string | null {
  const clean = text.trim().replace(/\s+/g, " ");
  const ok = clean.length > 0 && clean.length <= CUSTOM_MAX && clean.split(" ").length <= 6
    && /^[\p{L}\p{M}\p{N}'’ -]+$/u.test(clean) && /[\p{L}\p{N}]/u.test(clean);
  return ok ? clean : null;
}

/** The tier a generated story was made with, read back from its report so Save records the same one. */
export function requestedOf(report: GeneratedStory["report"]): DifficultyChoice {
  const r = (report as { difficulty?: { requested?: { tier?: string; length?: number; own_words?: number; uncommon_pct?: number } } }).difficulty?.requested;
  if (!r?.tier) return {};
  return r.tier === "custom" ? { difficulty: "custom", length: r.length, own_words: r.own_words, uncommon_pct: r.uncommon_pct } : { difficulty: r.tier };
}

/** The learner's own model that wrote a story, when it was one. */
export const ownModelName = (report: unknown): string | null => {
  const m = (report as { model?: { custom?: boolean; name?: string } } | undefined)?.model;
  return m?.custom ? m.name ?? null : null;
};
