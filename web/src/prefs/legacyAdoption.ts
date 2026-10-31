import { useEffect, useRef } from "react";
import type { User } from "../api/client";
import { LEGACY_THEME_KEY, legacyLanguageKey, type Prefs } from "./deviceCopy";

const LEGACY_THEMES = ["light", "dark", "system"];

/** Device-only settings from before preferences lived on the account: uploaded once, then removed. */
export function useLegacyAdoption(user: User | null, update: (changes: Partial<Prefs>, opts?: { now?: boolean }) => Promise<boolean>) {
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
}
