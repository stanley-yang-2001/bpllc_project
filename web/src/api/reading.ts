import { request } from "./http";
import type { GlossResult } from "./types";

export const readingApi = {
  /** Where the learner's own words stand in a text, with their meanings. No model is called. */
  gloss: (b: { language: string; text: string }) => request<GlossResult>("POST", "/reading/gloss", { json: b }),
};
