import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { posKey } from "../api/keys";
import type { MessageKey } from "../i18n/messages";

export const POS_KEYS = {
  noun: "pos.noun", verb: "pos.verb", adjective: "pos.adjective", adjective_i: "pos.adjective_i", adjective_na: "pos.adjective_na",
  adverb: "pos.adverb", pronoun: "pos.pronoun", determiner: "pos.determiner", article: "pos.article", preposition: "pos.preposition",
  conjunction: "pos.conjunction", interjection: "pos.interjection", particle: "pos.particle", measure_word: "pos.measure_word", phrase: "pos.phrase",
} as const satisfies Record<string, MessageKey>;

/** The categories words of this language can be labelled with. Each language has its own list (the server owns it). */
export function usePosCategories(language: string) {
  return useQuery({ queryKey: posKey(language), queryFn: () => api.partsOfSpeech(language), staleTime: Infinity });
}

export const posKeyOf = (code: string): MessageKey | null => (code in POS_KEYS ? POS_KEYS[code as keyof typeof POS_KEYS] : null);
