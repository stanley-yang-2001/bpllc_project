import type { MessageKey } from "../i18n/messages";

/** For each badge id: the message for its name and for how to earn it, and whether the message takes the number. */
const TEXT: Record<string, { name: MessageKey; how: MessageKey; n: boolean }> = {
  first_answer: { name: "rewards.badge.answers", how: "rewards.how.answers", n: false },
  known_10: { name: "rewards.badge.known", how: "rewards.how.known", n: true },
  known_50: { name: "rewards.badge.known", how: "rewards.how.known", n: true },
  known_100: { name: "rewards.badge.known", how: "rewards.how.known", n: true },
  known_250: { name: "rewards.badge.known", how: "rewards.how.known", n: true },
  streak_3: { name: "practice.progress.streak", how: "rewards.how.streak", n: true },
  streak_7: { name: "practice.progress.streak", how: "rewards.how.streak", n: true },
  streak_30: { name: "practice.progress.streak", how: "rewards.how.streak", n: true },
  first_story: { name: "rewards.badge.firstStory", how: "rewards.how.firstStory", n: false },
  stories_5: { name: "rewards.badge.stories", how: "rewards.how.stories", n: true },
  first_dictation: { name: "rewards.badge.dictation", how: "rewards.how.dictation", n: false },
  second_language: { name: "rewards.badge.languages", how: "rewards.how.languages", n: false },
};

type T = (key: MessageKey, params?: Record<string, string | number>) => string;

export function badgeText(id: string, target: number, t: T): { name: string; how: string } {
  const e = TEXT[id];
  if (!e) return { name: id, how: "" };          // a badge this version of the site does not know yet
  return { name: t(e.name, { n: target }), how: t(e.how, { n: target }) };
}
