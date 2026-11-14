import type { Entry } from "../practice/session";

/** How fancy a celebration is. 1 = a small label, 2 = label and sparkles, 3 = confetti, 4 = big confetti and a glow,
 * 5 = the full show (several bursts and a screen flash). The bigger the milestone, the higher the level. */
export type Level = 1 | 2 | 3 | 4 | 5;

/** Answers in a row (Hard, Good or Easy; Again ends the run) that earn a celebration. */
export const COMBO_LEVELS: Record<number, Level> = { 3: 1, 5: 2, 10: 3, 25: 4, 50: 5 };
/** Cards answered in one session that earn a celebration. */
export const CARDS_LEVELS: Record<number, Level> = { 10: 2, 25: 3, 50: 4, 100: 5 };
/** Reaching the daily goal. */
export const GOAL_LEVEL: Level = 4;

const BADGE_LEVELS: Record<string, Level> = {
  first_answer: 1, first_story: 2, first_dictation: 2, second_language: 2, known_10: 2, streak_3: 2,
  stories_5: 3, known_50: 3, streak_7: 3, known_100: 4, known_250: 5, streak_30: 5,
};
export const badgeLevel = (id: string): Level => BADGE_LEVELS[id] ?? 2;

/** Particles drawn for each level (index = level). Level 1 has none: just the label. */
export const PARTICLES = [0, 0, 12, 40, 90, 150];
/** How long each level stays on screen, in milliseconds. */
export const DURATION_MS = [0, 1800, 2400, 3000, 3800, 4800];

/** The length of the current run of answers that were not "Again", counted from the end of the session log. */
export function runLength(log: Entry[]): number {
  let n = 0;
  for (let i = log.length - 1; i >= 0 && log[i].grade >= 2; i--) n++;
  return n;
}

export interface Milestone { level: Level; kind: "combo" | "cards"; n: number }
/** What, if anything, the answer just given should celebrate. When both a run and a card count hit at once the bigger one wins. */
export function milestoneFor(log: Entry[]): Milestone | null {
  const combo = runLength(log), cards = log.length;
  const a: Milestone | null = COMBO_LEVELS[combo] && log[log.length - 1]?.grade >= 2 ? { level: COMBO_LEVELS[combo], kind: "combo", n: combo } : null;
  const b: Milestone | null = CARDS_LEVELS[cards] ? { level: CARDS_LEVELS[cards], kind: "cards", n: cards } : null;
  if (a && b) return b.level > a.level ? b : a;
  return a ?? b;
}
