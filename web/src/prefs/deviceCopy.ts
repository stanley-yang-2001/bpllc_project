/** The short-lived copy of the account's display preferences that this browser keeps so the page loads in the right
 * colours (public/theme-init.js reads it before the first paint). The account is the source of truth: the copy is
 * replaced whenever the account's values arrive, and wiped on logout, on a change of user and on any "not logged in"
 * answer, like all other per-user data (design 3H, section 12A). */
import type { Schemas } from "../api/client";

export type CustomColors = Schemas["CustomColors"];
export type Prefs = Schemas["PreferencesOut"];

export const COPY_KEY = "tutor:prefs:cache";
/** Device-only settings of the first design. They are uploaded to the account once and then removed. */
export const LEGACY_THEME_KEY = "tutor:theme";
export const legacyLanguageKey = (userId: number) => `tutor:lang:${userId}`;

export interface DeviceCopy {
  userId: number;
  theme: string;
  active_language: string | null;
  ui_follows_study_language: boolean;
  custom_colors: CustomColors | null;
  /** The derived colour map of a preset or custom theme, applied by the init script with no colour maths of its own. */
  vars: Record<string, string> | null;
  /** "dark" or "light": which base the init script sets, so the right `.dark` class is there before the first paint. */
  base: "light" | "dark" | null;
}

export function readCopy(): DeviceCopy | null {
  try {
    const raw = localStorage.getItem(COPY_KEY);
    if (!raw) return null;
    const v = JSON.parse(raw);
    if (!v || typeof v !== "object" || typeof v.userId !== "number" || typeof v.theme !== "string") return null;
    return {
      userId: v.userId,
      theme: v.theme,
      active_language: typeof v.active_language === "string" ? v.active_language : null,
      ui_follows_study_language: v.ui_follows_study_language === true,
      custom_colors: v.custom_colors && typeof v.custom_colors === "object" ? v.custom_colors : null,
      vars: v.vars && typeof v.vars === "object" ? v.vars : null,
      base: v.base === "dark" || v.base === "light" ? v.base : null,
    };
  } catch {
    return null;
  }
}

/** Writes `change` over the copy that belongs to the same person; a copy of anyone else is replaced, never merged. */
export function writeCopy(userId: number, change: Partial<Omit<DeviceCopy, "userId">>) {
  try {
    const old = readCopy();
    const base: DeviceCopy = old && old.userId === userId ? old
      : { userId, theme: "system", active_language: null, ui_follows_study_language: false, custom_colors: null, vars: null, base: null };
    const next = JSON.stringify({ ...base, ...change, userId });
    if (localStorage.getItem(COPY_KEY) !== next) localStorage.setItem(COPY_KEY, next);   // no write, no storage event
  } catch { /* storage blocked: the page just loads in the default colours first */ }
}

export function wipeCopy() {
  try { localStorage.removeItem(COPY_KEY); } catch { /* nothing to wipe */ }
}
