import { qs, request } from "./http";
import type { Picture, Word, WordOfDay, WordPage, UploadResult, WordSet, SetList, StarterPackList, StarterAdded, SetFilter, DefineResult } from "./types";

export const wordsApi = {
  words: (p: { language: string; q?: string; limit?: number; offset?: number; set?: SetFilter; missing_meaning?: boolean }) =>
    request<WordPage>("GET", `/words?${qs({ ...p, set: p.set === "all" ? undefined : p.set, missing_meaning: p.missing_meaning ? "true" : undefined })}`),
  wordOfTheDay: (language: string) => request<WordOfDay>("GET", `/words/today?${qs({ language })}`),
  starterPacks: (language: string) => request<StarterPackList>("GET", `/words/starter-packs?${qs({ language })}`),
  addStarterPack: (b: { language: string; pack: string }) => request<StarterAdded>("POST", "/words/starter-packs", { json: b }),
  addWord: (b: { language: string; word: string; meaning?: string; set_id?: number | null; pos?: string }) => request<Word>("POST", "/words", { json: b }),
  editWord: (id: number, b: { word?: string; meaning?: string | null; pos?: string | null }) =>
    request<Word>("PATCH", `/words/${id}`, { json: b }),
  deleteWords: (ids: number[]) => request<{ deleted: number }>("POST", "/words/delete", { json: { ids } }),
  sets: (language: string) => request<SetList>("GET", `/sets?${qs({ language })}`),
  createSet: (b: { language: string; name: string }) => request<WordSet>("POST", "/sets", { json: b }),
  renameSet: (id: number, name: string) => request<WordSet>("PATCH", `/sets/${id}`, { json: { name } }),
  deleteSet: (id: number) => request<{ moved_to_general: number }>("DELETE", `/sets/${id}`),
  /** set_id null = back to General */
  moveWords: (ids: number[], set_id: number | null) => request<{ moved: number }>("POST", "/words/move", { json: { ids, set_id } }),
  /** Asks the tutor to write meanings for up to 25 words with none; call again while `remaining` is above 0. */
  defineWords: (b: { language: string; ids?: number[]; set?: SetFilter; meaning_mode?: "native" | "study" | "both" }) =>
    request<DefineResult>("POST", "/words/define", { json: { ...b, set: b.set === undefined ? undefined : String(b.set) } }),
  /** Asks the tutor to label up to 25 words that have no part of speech; call again while `remaining` is above 0. */
  labelWords: (b: { language: string; ids?: number[]; set?: SetFilter }) =>
    request<DefineResult>("POST", "/words/label", { json: { ...b, set: b.set === undefined ? undefined : String(b.set) } }),
  partsOfSpeech: (language: string) => request<{ language: string; items: string[] }>("GET", `/words/parts-of-speech?${qs({ language })}`),
  /** A word's picture is one emoji, or one photo (kept small, with its camera and location data removed by the server). Either replaces what was there. */
  setEmoji: (id: number, emoji: string) => request<Picture>("PUT", `/words/${id}/picture/emoji`, { json: { emoji } }),
  setPhoto: (id: number, photo: Blob) => {
    const form = new FormData();
    form.set("file", photo, "photo.jpg");
    return request<Picture>("PUT", `/words/${id}/picture/photo`, { form });
  },
  removePicture: (id: number) => request<void>("DELETE", `/words/${id}/picture`),
  uploadWords: (language: string, file: File) => {
    const form = new FormData();
    form.set("language", language);
    form.set("file", file);
    return request<UploadResult>("POST", "/words/upload", { form });
  },
};
