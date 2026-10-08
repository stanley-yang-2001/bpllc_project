import type { components } from "./schema";

export type Schemas = components["schemas"];
export type User = Schemas["UserOut"];
export type Word = Schemas["WordOut"];
export type WordPage = Schemas["WordPage"];
export type UploadResult = Schemas["UploadResult"];
export type LanguageInfo = Schemas["LanguageOut"];
export type Health = Schemas["HealthOut"];
export type Meta = Schemas["MetaOut"];

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
  updateProfile: (b: { display_name?: string; native_language?: string }) => request<User>("PATCH", "/me", { json: b }),
  changeEmail: (b: { email: string; password: string }) => request<User>("POST", "/me/email", { json: b }),
  changePassword: (b: { current_password: string; new_password: string }) => request<void>("POST", "/me/password", { json: b }),
  deleteAccount: (password: string) => request<void>("POST", "/me/delete", { json: { password } }),
  exportData: () => request<unknown>("GET", "/me/export"),
  logout: () => request<void>("POST", "/auth/logout", { skipExpected: true }),
  logoutAll: () => request<void>("POST", "/auth/logout-all"),
  addLanguage: (language: string) => request<User>("POST", "/me/languages", { json: { language } }),
  languages: () => request<LanguageInfo[]>("GET", "/languages"),
  words: (p: { language: string; q?: string; limit?: number; offset?: number }) =>
    request<WordPage>("GET", `/words?${qs(p)}`),
  addWord: (b: { language: string; word: string; meaning?: string }) => request<Word>("POST", "/words", { json: b }),
  editWord: (id: number, b: { word?: string; meaning?: string | null }) =>
    request<Word>("PATCH", `/words/${id}`, { json: b }),
  deleteWords: (ids: number[]) => request<{ deleted: number }>("POST", "/words/delete", { json: { ids } }),
  uploadWords: (language: string, file: File) => {
    const form = new FormData();
    form.set("language", language);
    form.set("file", file);
    return request<UploadResult>("POST", "/words/upload", { form });
  },
  health: () => request<Health>("GET", "/health"),
};
