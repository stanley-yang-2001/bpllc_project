import type { components } from "./schema";

export type Schemas = components["schemas"];
export type User = Schemas["UserOut"];
export type Word = Schemas["WordOut"];
export type WordPage = Schemas["WordPage"];
export type UploadResult = Schemas["UploadResult"];
export type LanguageInfo = Schemas["LanguageOut"];
export type Health = Schemas["HealthOut"];
export type Meta = Schemas["MetaOut"];
export type Policy = Schemas["PolicyOut"];
export type Preferences = Schemas["PreferencesOut"];
export type ChatReply = Schemas["ChatOut"];
export type ToolCall = Schemas["ToolCallOut"];
export type StoryOptions = Schemas["StoryOptionsOut"];
/** The learner's difficulty choice: a preset name, or "custom" with their own numbers. Left out = no tier. */
export interface DifficultyChoice { difficulty?: string; length?: number; own_words?: number; uncommon_pct?: number }
export type MyModel = { enabled: boolean; configured: boolean; model: string | null; base_url: string | null; key_last4: string | null; has_key: boolean };
export type GeneratedStory = Schemas["GeneratedStoryOut"];
export type SavedStory = Schemas["StoryFull"];
export type StoryPage = Schemas["StoryPage"];
export type StoryCard = Schemas["StoryCard"];
export type FlashcardSet = Schemas["FlashcardSet"];
export type ClozeSet = Schemas["ClozeSet"];
export type ClozeItem = Schemas["ClozeItem"];
export type WordSet = Schemas["SetOut"];
export type Pronunciation = Schemas["PronounceOut"];
export type Translation = Schemas["TranslateOut"];
export type SetList = Schemas["SetList"];
export type ChoiceSet = Schemas["ChoiceSet"];
export type PracticeProgress = Schemas["ProgressOut"];
export interface Answer { word_id: number; correct: boolean }
export type ChoiceCard = Schemas["ChoiceOut"];
/** Which words to show or practise: every word, the General set, or one set by id (sent as "all", "general" or the number). */
export type SetFilter = "all" | "general" | number;
export interface DefineResult { defined: number; failed: number; remaining: number }

/** Every non-2xx response from the API has the same body: {error: {code, message, retry_after?}}. */
export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public retryAfter?: number) {
    super(message);
  }
}

/** The id of the user this tab is showing. Sent with every request so that, if someone else logs in on another
 * tab (browsers share one cookie across tabs), this tab is refused instead of acting as the wrong person. */
let currentUserId: number | null = null;
export const setCurrentUserId = (id: number | null) => { currentUserId = id; };

interface Opts { json?: unknown; form?: FormData; skipExpected?: boolean }

async function request<T>(method: string, path: string, opts: Opts = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (currentUserId !== null && !opts.skipExpected) headers["X-Expected-User"] = String(currentUserId);
  let body: BodyInit | undefined;
  if (method !== "GET") headers["X-Requested-With"] = "tutor"; // CSRF defence: the API rejects non-GET without it
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  } else if (opts.form) {
    body = opts.form;
  }
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { method, headers, body, credentials: "same-origin" });
  } catch {
    throw new ApiError(0, "network_error", "Can't reach the server. Is it running?");
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const e = data?.error;
    throw new ApiError(res.status, e?.code ?? "error", e?.message ?? `Request failed (${res.status})`, e?.retry_after);
  }
  return data as T;
}

const qs = (params: Record<string, string | number | undefined>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") p.set(k, String(v));
  return p.toString();
};

export const api = {
  me: () => request<User>("GET", "/me", { skipExpected: true }), // how a tab learns who is really logged in
  register: (b: { email: string; password: string; display_name: string; language: string; accept_privacy: boolean }) =>
    request<User>("POST", "/auth/register", { json: b, skipExpected: true }),
  login: (b: { email: string; password: string }) => request<User>("POST", "/auth/login", { json: b, skipExpected: true }),
  meta: () => request<Meta>("GET", "/meta", { skipExpected: true }),
  policy: (lang?: string) => request<Policy>("GET", `/policy${lang ? `?lang=${encodeURIComponent(lang)}` : ""}`, { skipExpected: true }),
  updateProfile: (b: { display_name?: string; native_language?: string }) => request<User>("PATCH", "/me", { json: b }),
  savePreferences: (b: Partial<Preferences>) => request<Preferences>("PATCH", "/me/preferences", { json: b }),
  changeEmail: (b: { email: string; password: string }) => request<User>("POST", "/me/email", { json: b }),
  changePassword: (b: { current_password: string; new_password: string }) => request<void>("POST", "/me/password", { json: b }),
  deleteAccount: (password: string) => request<void>("POST", "/me/delete", { json: { password } }),
  myModel: () => request<MyModel>("GET", "/me/model"),
  saveMyModel: (b: { model: string; base_url: string; api_key?: string; remove_key?: boolean }) => request<MyModel>("PUT", "/me/model", { json: b }),
  testMyModel: (b: { model: string; base_url: string; api_key?: string; remove_key?: boolean }) => request<{ ok: boolean }>("POST", "/me/model/test", { json: b }),
  removeMyModel: () => request<void>("DELETE", "/me/model"),
  exportData: () => request<unknown>("GET", "/me/export"),
  logout: () => request<void>("POST", "/auth/logout", { skipExpected: true }),
  logoutAll: () => request<void>("POST", "/auth/logout-all"),
  addLanguage: (language: string) => request<User>("POST", "/me/languages", { json: { language } }),
  languages: () => request<LanguageInfo[]>("GET", "/languages"),
  words: (p: { language: string; q?: string; limit?: number; offset?: number; set?: SetFilter; missing_meaning?: boolean }) =>
    request<WordPage>("GET", `/words?${qs({ ...p, set: p.set === "all" ? undefined : p.set, missing_meaning: p.missing_meaning ? "true" : undefined })}`),
  addWord: (b: { language: string; word: string; meaning?: string; set_id?: number | null }) => request<Word>("POST", "/words", { json: b }),
  editWord: (id: number, b: { word?: string; meaning?: string | null }) =>
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
  uploadWords: (language: string, file: File) => {
    const form = new FormData();
    form.set("language", language);
    form.set("file", file);
    return request<UploadResult>("POST", "/words/upload", { form });
  },
  chat: (b: { message: string; language: string; session_id: string; set_ids?: number[] }) => request<ChatReply>("POST", "/chat", { json: b }),
  storyOptions: () => request<StoryOptions>("GET", "/stories/options"),
  generateStory: (b: { language: string; story_type?: string; topic?: string; set_ids?: number[] } & DifficultyChoice) =>
    request<GeneratedStory>("POST", "/stories/generate", { json: b }),
  saveStory: (b: { language: string; body: string; story_type?: string | null; topic?: string | null; model?: string | null } & DifficultyChoice) =>
    request<SavedStory>("POST", "/stories", { json: b }),
  stories: (p: { language?: string; limit?: number; offset?: number }) => request<StoryPage>("GET", `/stories?${qs(p)}`),
  story: (id: number) => request<SavedStory>("GET", `/stories/${id}`),
  deleteStory: (id: number) => request<void>("DELETE", `/stories/${id}`),
  flashcards: (p: { language: string; limit?: number; set?: SetFilter; due?: boolean }) =>
    request<FlashcardSet>("GET", `/practice/flashcards?${qs({ ...p, set: p.set === "all" ? undefined : p.set, due: p.due ? "true" : undefined })}`),
  choices: (p: { language: string; limit?: number; direction?: "meaning" | "word"; set?: SetFilter; due?: boolean }) =>
    request<ChoiceSet>("GET", `/practice/choices?${qs({ ...p, set: p.set === "all" ? undefined : p.set, due: p.due ? "true" : undefined })}`),
  recordAnswers: (answers: Answer[]) => request<void>("POST", "/practice/answers", { json: { answers } }),
  practiceProgress: (language: string) => request<PracticeProgress>("GET", `/practice/progress?${qs({ language })}`),
  cloze: (storyId: number) => request<ClozeSet>("GET", `/practice/cloze?story_id=${storyId}`),
  pronounce: (b: { language: string; texts: string[] }) => request<Pronunciation>("POST", "/pronounce", { json: b }),
  translate: (b: { language: string; target_language: string; texts: string[]; words?: boolean }) => request<Translation>("POST", "/translate", { json: b }),
  health: () => request<Health>("GET", "/health"),
};
