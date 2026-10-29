/** Every cached per-learner query is keyed by the user id, so data fetched for one person can never be read
 * (or overwritten by a slow response) under another person's key. */
export const wordsKey = (userId: number, language: string, ...rest: (string | number)[]) =>
  ["words", userId, language, ...rest] as const;
export const storiesKey = (userId: number, ...rest: (string | number)[]) => ["stories", userId, ...rest] as const;
export const setsKey = (userId: number, language: string) => ["sets", userId, language] as const;
/** What the learner has practised (counts, streak). Dropped whenever an answer is recorded. */
export const progressKey = (userId: number, language: string) => ["practice", userId, "progress", language] as const;
export const starterKey = (userId: number, language: string) => ["starter", userId, language] as const;
