import { request } from "./http";
import type { Pronunciation, Translation } from "./types";

export const textApi = {
  pronounce: (b: { language: string; texts: string[] }) => request<Pronunciation>("POST", "/pronounce", { json: b }),
  translate: (b: { language: string; target_language: string; texts: string[]; words?: boolean }) => request<Translation>("POST", "/translate", { json: b }),
};
