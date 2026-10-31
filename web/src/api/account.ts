import { request } from "./http";
import type { User, LanguageInfo, Health, Meta, Policy, Preferences } from "./types";

export const accountApi = {
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
  exportData: () => request<unknown>("GET", "/me/export"),
  logout: () => request<void>("POST", "/auth/logout", { skipExpected: true }),
  logoutAll: () => request<void>("POST", "/auth/logout-all"),
  addLanguage: (language: string) => request<User>("POST", "/me/languages", { json: { language } }),
  languages: () => request<LanguageInfo[]>("GET", "/languages"),
  health: () => request<Health>("GET", "/health"),
};
