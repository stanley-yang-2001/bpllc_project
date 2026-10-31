import { createContext, useContext, useMemo, type ReactNode } from "react";
import { useAuth } from "../auth/AuthContext";
import type { Prefs } from "./deviceCopy";
import { useFollowOtherTabs, useWriteDeviceCopy } from "./deviceSync";
import { useLegacyAdoption } from "./legacyAdoption";
import { useSavedPreferences } from "./useSavedPreferences";

export const DEFAULT_PREFS: Prefs = { active_language: null, ui_follows_study_language: false, chat_in_study_language: false, meaning_mode: "native", theme: "system", custom_colors: null };

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

/**
 * The single source of display preferences (design 3H). Theme and active-language providers are readers of it.
 * Holding is here (defaults, the account's values, unsaved changes merged); saving, the device copy and the one-time
 * adoption of old device settings are one hook each.
 */
export function PreferencesProvider({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const userId = user?.id ?? null;
  const { overrides, update, saveFailed } = useSavedPreferences(userId);

  const serverPrefs = user?.preferences ?? null;
  const prefs = useMemo<Prefs>(
    () => ({ ...DEFAULT_PREFS, ...(serverPrefs ?? {}), ...(overrides.userId === userId && userId !== null ? overrides.values : {}) }),
    [serverPrefs, overrides, userId],
  );

  useWriteDeviceCopy(loading, userId, prefs);
  useFollowOtherTabs(userId);
  useLegacyAdoption(user, update);

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
