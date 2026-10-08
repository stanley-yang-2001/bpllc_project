import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type Theme = "light" | "dark" | "system";
export const THEME_KEY = "tutor:theme";

const prefersDark = () => typeof window.matchMedia === "function" && window.matchMedia("(prefers-color-scheme: dark)").matches;
export const resolveTheme = (t: Theme): "light" | "dark" => (t === "system" ? (prefersDark() ? "dark" : "light") : t);

function readStored(): Theme {
  try {
    const v = localStorage.getItem(THEME_KEY);
    return v === "light" || v === "dark" || v === "system" ? v : "system";
  } catch {
    return "system";
  }
}

interface Value { theme: Theme; resolved: "light" | "dark"; setTheme: (t: Theme) => void }
const Ctx = createContext<Value | null>(null);

/** The theme is a device preference (like the language of the interface), not account data, so it is kept
 * per browser and survives logout. */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(readStored);
  const [resolved, setResolved] = useState<"light" | "dark">(() => resolveTheme(readStored()));

  useEffect(() => {
    const apply = () => {
      const r = resolveTheme(theme);
      setResolved(r);
      document.documentElement.classList.toggle("dark", r === "dark");
    };
    apply();
    if (theme !== "system" || typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", apply);                      // follow the OS while on "System"
    return () => mq.removeEventListener("change", apply);
  }, [theme]);

  useEffect(() => {                                            // another tab changed it
    const onStorage = (e: StorageEvent) => { if (e.key === THEME_KEY) setThemeState(readStored()); };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const setTheme = useCallback((t: Theme) => {
    setThemeState(t);
    try { localStorage.setItem(THEME_KEY, t); } catch { /* private mode: applies for this visit only */ }
  }, []);

  const value = useMemo(() => ({ theme, resolved, setTheme }), [theme, resolved, setTheme]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useTheme(): Value {
  const v = useContext(Ctx);
  if (!v) throw new Error("useTheme must be used inside <ThemeProvider>");
  return v;
}
