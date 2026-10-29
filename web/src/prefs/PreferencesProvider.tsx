import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, type User } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { COPY_KEY, LEGACY_THEME_KEY, legacyLanguageKey, readCopy, wipeCopy, writeCopy, type Prefs } from "./deviceCopy";

export const DEFAULT_PREFS: Prefs = { active_language: null, ui_follows_study_language: false, chat_in_study_language: false, meaning_mode: "native", theme: "system", custom_colors: null };
const SAVE_DELAY_MS = 600;
const LEGACY_THEMES = ["light", "dark", "system"];

interface Value {
  /** What to show now: the account's values with this person's unsaved changes on top; defaults when nobody is signed in. */
  prefs: Prefs;
  /** False until the first "who is signed in" answer has arrived. */
  ready: boolean;
  loggedIn: boolean;
  /** Applies at once and saves after a short pause (or at once with `now`). Resolves to whether the save worked. */
  update: (changes: Partial<Prefs>, opts?: { now?: boolean }) => Promise<boolean>;
  /** True after a save failed. The look stays as chosen; the next change tries again. */
  saveFailed: boolean;
}
const Ctx = createContext<Value | null>(null);

type Overrides = { userId: number | null; values: Partial<Prefs> };

/** The single source of display preferences (design 3H). Theme and active-language providers are readers of it. */
export function PreferencesProvider({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const qc = useQueryClient();
  const userId = user?.id ?? null;
  const [overrides, setOverrides] = useState<Overrides>({ userId: null, values: {} });
  const [saveFailed, setSaveFailed] = useState(false);
  const pending = useRef<Partial<Prefs>>({});
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const inflight = useRef(false);
  const again = useRef(false);
  const owner = useRef<number | null>(userId);
  owner.current = userId;

  // Another person, or nobody: an unsaved change of the previous person must never be saved into this account.
  useEffect(() => {
    pending.current = {};
    again.current = false;
    if (timer.current) { clearTimeout(timer.current); timer.current = undefined; }
    setOverrides({ userId: null, values: {} });
    setSaveFailed(false);
  }, [userId]);

  const flush = useCallback(async (): Promise<boolean> => {
    if (timer.current) { clearTimeout(timer.current); timer.current = undefined; }
    if (inflight.current) { again.current = true; return false; }
    const batch = pending.current;
    const who = owner.current;
    if (who === null || Object.keys(batch).length === 0) return true;
    pending.current = {};
    inflight.current = true;
    let ok = false;
    try {
      const saved = await api.savePreferences(batch);
      if (owner.current !== who) return false;
      qc.setQueryData<User | null>(["me"], (me) => (me && me.id === who ? { ...me, preferences: saved } : me));
      // Keep a local value only if it changed again after this request left.
      setOverrides((o) => {
        if (o.userId !== who) return o;
        const values: Partial<Prefs> = { ...o.values };
        for (const k of Object.keys(batch) as (keyof Prefs)[]) if (!(k in pending.current)) delete values[k];
        return { userId: who, values };
      });
      setSaveFailed(false);
      ok = true;
    } catch {
      if (owner.current === who) {
        pending.current = { ...batch, ...pending.current };      // newer values win; the next change retries the lot
        setSaveFailed(true);
      }
    } finally {
      inflight.current = false;
      if (again.current) { again.current = false; void flush(); }
    }
    return ok;
  }, [qc]);

  const update = useCallback((changes: Partial<Prefs>, opts?: { now?: boolean }): Promise<boolean> => {
    const who = owner.current;
    if (who === null) return Promise.resolve(false);
    pending.current = { ...pending.current, ...changes };
    setOverrides((o) => ({ userId: who, values: { ...(o.userId === who ? o.values : {}), ...changes } }));
    if (opts?.now) return flush();
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => { void flush(); }, SAVE_DELAY_MS);
    return Promise.resolve(true);
  }, [flush]);

  const serverPrefs = user?.preferences ?? null;
  const prefs = useMemo<Prefs>(
    () => ({ ...DEFAULT_PREFS, ...(serverPrefs ?? {}), ...(overrides.userId === userId && userId !== null ? overrides.values : {}) }),
    [serverPrefs, overrides, userId],
  );

  // The device copy follows the account; nobody signed in means no copy at all.
  useEffect(() => {
    if (loading) return;
    if (userId === null) { wipeCopy(); return; }
    writeCopy(userId, {
      theme: prefs.theme, custom_colors: prefs.custom_colors,
      active_language: prefs.active_language, ui_follows_study_language: prefs.ui_follows_study_language,
    });
  }, [loading, userId, prefs]);

  // Another tab changed the copy for this same person: follow it.
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key !== COPY_KEY || userId === null) return;
      const copy = readCopy();
      if (!copy || copy.userId !== userId) return;
      qc.setQueryData<User | null>(["me"], (me) => me && me.id === userId ? {
        ...me,
        preferences: {
          chat_in_study_language: me.preferences?.chat_in_study_language ?? false,
          meaning_mode: me.preferences?.meaning_mode ?? "native",
          theme: copy.theme, custom_colors: copy.custom_colors,
          active_language: copy.active_language, ui_follows_study_language: copy.ui_follows_study_language,
        },
      } : me);
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [qc, userId]);

  // Device-only settings from before preferences lived on the account: uploaded once, then removed.
  const adopted = useRef<number | null>(null);
  useEffect(() => {
    if (!user || adopted.current === user.id) return;
    adopted.current = user.id;
    let theme: string | null = null;
    let language: string | null = null;
    try {
      theme = localStorage.getItem(LEGACY_THEME_KEY);
      language = localStorage.getItem(legacyLanguageKey(user.id));
    } catch { return; }
    const forget = () => {
      try { localStorage.removeItem(LEGACY_THEME_KEY); localStorage.removeItem(legacyLanguageKey(user.id)); } catch { /* nothing */ }
    };
    if (user.preferences !== null) { forget(); return; }       // the account already has its own: the old values are stale
    const changes: Partial<Prefs> = {};
    if (theme && LEGACY_THEMES.includes(theme)) changes.theme = theme;
    if (language && user.languages.includes(language)) changes.active_language = language;
    if (Object.keys(changes).length === 0) { forget(); return; }
    void update(changes, { now: true }).then((ok) => { if (ok) forget(); });
  }, [user, update]);

  const value = useMemo<Value>(
    () => ({ prefs, ready: !loading, loggedIn: userId !== null, update, saveFailed }),
    [prefs, loading, userId, update, saveFailed],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function usePreferences(): Value {
  const v = useContext(Ctx);
  if (!v) throw new Error("usePreferences must be used inside <PreferencesProvider>");
  return v;
}
