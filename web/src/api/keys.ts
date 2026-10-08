/** Every cached per-learner query is keyed by the user id, so data fetched for one person can never be read
 * (or overwritten by a slow response) under another person's key. */
export const wordsKey = (userId: number, language: string, ...rest: (string | number)[]) =>
  ["words", userId, language, ...rest] as const;
