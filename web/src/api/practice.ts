import { qs, request } from "./http";
import type { FlashcardSet, ClozeSet, ChoiceSet, PosSet, DictationSet, PracticeProgress, Answer, SetFilter, FlashcardScope, Review, ReviewResult, StudyStats, HardWords } from "./types";

const setParam = (set?: SetFilter) => (set === "all" ? undefined : set);

export const practiceApi = {
  /** No limit unless one is asked for. scope "ids" needs `ids`. */
  flashcards: (p: { language: string; limit?: number; set?: SetFilter; due?: boolean; scope?: FlashcardScope; ids?: number[] }) =>
    request<FlashcardSet>("GET", `/practice/flashcards?${qs({ language: p.language, limit: p.limit, set: setParam(p.set), due: p.due ? "true" : undefined, scope: p.scope, ids: p.ids?.join(",") })}`),
  /** Graded flashcard answers with how long they took; says when each word is due again. */
  recordReviews: (reviews: Review[]) => request<{ results: ReviewResult[] }>("POST", "/practice/reviews", { json: { reviews } }).then((r) => r.results),
  studyStats: (language: string, set?: SetFilter) => request<StudyStats>("GET", `/practice/stats?${qs({ language, set: setParam(set) })}`),
  hardestWords: (language: string, set?: SetFilter, limit = 10) => request<HardWords>("GET", `/practice/hardest?${qs({ language, set: setParam(set), limit })}`),
  choices: (p: { language: string; limit?: number; direction?: "meaning" | "word"; set?: SetFilter; due?: boolean }) =>
    request<ChoiceSet>("GET", `/practice/choices?${qs({ ...p, set: p.set === "all" ? undefined : p.set, due: p.due ? "true" : undefined })}`),
  dictation: (p: { language: string; limit?: number; set?: SetFilter; due?: boolean }) =>
    request<DictationSet>("GET", `/practice/dictation?${qs({ ...p, set: p.set === "all" ? undefined : p.set, due: p.due ? "true" : undefined })}`),
  posCards: (p: { language: string; limit?: number; set?: SetFilter; due?: boolean }) =>
    request<PosSet>("GET", `/practice/pos?${qs({ ...p, set: p.set === "all" ? undefined : p.set, due: p.due ? "true" : undefined })}`),
  recordAnswers: (answers: Answer[]) => request<void>("POST", "/practice/answers", { json: { answers } }),
  practiceProgress: (language: string, set?: SetFilter) => request<PracticeProgress>("GET", `/practice/progress?${qs({ language, set: setParam(set) })}`),
  cloze: (storyId: number) => request<ClozeSet>("GET", `/practice/cloze?story_id=${storyId}`),
};
