import { qs, request } from "./http";
import type { FlashcardSet, ClozeSet, ChoiceSet, PosSet, DictationSet, PracticeProgress, Answer, SetFilter } from "./types";

export const practiceApi = {
  flashcards: (p: { language: string; limit?: number; set?: SetFilter; due?: boolean }) =>
    request<FlashcardSet>("GET", `/practice/flashcards?${qs({ ...p, set: p.set === "all" ? undefined : p.set, due: p.due ? "true" : undefined })}`),
  choices: (p: { language: string; limit?: number; direction?: "meaning" | "word"; set?: SetFilter; due?: boolean }) =>
    request<ChoiceSet>("GET", `/practice/choices?${qs({ ...p, set: p.set === "all" ? undefined : p.set, due: p.due ? "true" : undefined })}`),
  dictation: (p: { language: string; limit?: number; set?: SetFilter; due?: boolean }) =>
    request<DictationSet>("GET", `/practice/dictation?${qs({ ...p, set: p.set === "all" ? undefined : p.set, due: p.due ? "true" : undefined })}`),
  posCards: (p: { language: string; limit?: number; set?: SetFilter; due?: boolean }) =>
    request<PosSet>("GET", `/practice/pos?${qs({ ...p, set: p.set === "all" ? undefined : p.set, due: p.due ? "true" : undefined })}`),
  recordAnswers: (answers: Answer[]) => request<void>("POST", "/practice/answers", { json: { answers } }),
  practiceProgress: (language: string) => request<PracticeProgress>("GET", `/practice/progress?${qs({ language })}`),
  cloze: (storyId: number) => request<ClozeSet>("GET", `/practice/cloze?story_id=${storyId}`),
};
