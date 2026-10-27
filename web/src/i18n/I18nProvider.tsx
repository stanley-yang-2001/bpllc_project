import { createContext, useContext, useEffect, useMemo, type ReactNode } from "react";
import { ApiError } from "../api/client";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { usePreferences } from "../prefs/PreferencesProvider";
import { LOCALES, MESSAGES, type Locale, type MessageKey } from "./messages";

export type Params = Record<string, string | number>;

/** One message in one locale: the locale's own text, else English, else the key itself (never blank). */
export function translate(locale: Locale, key: string, params?: Params): string {
  const row = (MESSAGES as Record<string, readonly string[]>)[key];
  const text = row ? (row[LOCALES.indexOf(locale)] ?? row[0]) : key;
  return params ? text.replace(/\{(\w+)\}/g, (m, k: string) => (k in params ? String(params[k]) : m)) : text;
}

/** Plural form: `<base>.one` or `<base>.other`, picked by the locale's own plural rules. */
export function translateCount(locale: Locale, base: string, count: number, params?: Params): string {
  const form = new Intl.PluralRules(locale).select(count) === "one" ? "one" : "other";
  return translate(locale, `${base}.${form}`, { count, ...params });
}

/** Error text by code. Only codes in the catalog are translated; any other server message is shown as the server wrote it. */
export function codeMessage(locale: Locale, code: string | undefined, message: string | undefined, fallbackKey: MessageKey = "error.generic"): string {
  if (code && `error.${code}` in MESSAGES) return translate(locale, `error.${code}`);
  return message || translate(locale, fallbackKey);
}
export function errorMessage(locale: Locale, e: unknown, fallbackKey: MessageKey = "error.generic"): string {
  return e instanceof ApiError ? codeMessage(locale, e.code, e.message, fallbackKey) : translate(locale, fallbackKey);
}

type PluralBase = "report.outside" | "vocab.deleted" | "sets.moved";
export const htmlLang = (l: Locale) => (l === "zh" ? "zh-Hans" : l);

interface Value {
  locale: Locale;
  t: (key: MessageKey, params?: Params) => string;
  tc: (base: PluralBase, count: number, params?: Params) => string;
  err: (e: unknown, fallbackKey?: MessageKey) => string;
  code: (code: string | undefined, message: string | undefined) => string;
}
const Ctx = createContext<Value | null>(null);

/** The site's language: the study language when the learner has switched that on and we have a translation for it,
 * otherwise English. Signed out, it is always English (the sign-in pages stay English, design 3F). */
export function I18nProvider({ children }: { children: ReactNode }) {
  const { prefs, loggedIn } = usePreferences();
  const { active } = useActiveLanguage();
  const locale: Locale =
    loggedIn && prefs.ui_follows_study_language && (LOCALES as readonly string[]).includes(active) ? (active as Locale) : "en";

  useEffect(() => { document.documentElement.lang = htmlLang(locale); }, [locale]);

  const value = useMemo<Value>(() => ({
    locale,
    t: (key, params) => translate(locale, key, params),
    tc: (base, count, params) => translateCount(locale, base, count, params),
    err: (e, fallbackKey) => errorMessage(locale, e, fallbackKey),
    code: (c, m) => codeMessage(locale, c, m),
  }), [locale]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useI18n(): Value {
  const v = useContext(Ctx);
  if (!v) throw new Error("useI18n must be used inside <I18nProvider>");
  return v;
}
// kept for callers that want a stable reference
export const useT = () => useI18n().t;
