import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useAuth } from "../auth/AuthContext";
import { writeCopy } from "../prefs/deviceCopy";
import { usePreferences } from "../prefs/PreferencesProvider";
import { DEFAULT_CUSTOM, derivePalette, isPreset, PRESETS, validColors, type Colors, type Palette } from "./palette";

/** A built-in (`light`, `dark`, `system`), a preset id, or `custom`. */
export type Theme = string;
const BUILT_IN = ["light", "dark", "system"];
const ALL_VARS = Object.keys(derivePalette(DEFAULT_CUSTOM).vars);
/** Where the light/dark switch on the sign-in and policy pages keeps its choice: this tab only, never remembered. */
export const TEMP_THEME_KEY = "tutor:theme:tab";

const prefersDark = () => typeof window.matchMedia === "function" && window.matchMedia("(prefers-color-scheme: dark)").matches;
export const resolveTheme = (t: Theme): "light" | "dark" => (t === "system" ? (prefersDark() ? "dark" : "light") : t === "dark" ? "dark" : "light");
/** A theme id this version of the app does not know (a newer app saved it) means System, never a broken page. */
export const asTheme = (v: unknown): Theme => (typeof v === "string" && (BUILT_IN.includes(v) || v === "custom" || isPreset(v)) ? v : "system");
/** The sign-in pages only have the three built-ins. */
const asBuiltIn = (v: unknown): Theme => (typeof v === "string" && BUILT_IN.includes(v) ? v : "system");

/** The five colours behind a preset or custom theme; null for the built-ins, which have no overrides. */
export function themeColors(theme: Theme, custom: unknown): Colors | null {
  if (isPreset(theme)) return PRESETS[theme].colors;
  if (theme === "custom") return validColors(custom) ?? DEFAULT_CUSTOM;
  return null;
}

function readTemp(): Theme {
  try { return asBuiltIn(sessionStorage.getItem(TEMP_THEME_KEY)); } catch { return "system"; }
}

interface Value {
  theme: Theme;
  resolved: "light" | "dark";
  setTheme: (t: Theme) => void;
  /** The colours being shown (preset or custom), with whether the accent had to be darkened; null on a built-in. */
  colors: Colors | null;
  palette: Palette | null;
  /** The learner's own five colours (what "Custom" shows), whether or not Custom is the chosen theme. */
  customColors: Colors;
  setCustomColors: (c: Colors) => void;
}
const Ctx = createContext<Value | null>(null);

/** A reader of the account's preferences (design 3H). Signed in, the choice is the account's and follows the learner
 * to every device. Signed out, the page follows the operating system and the switch is for this tab only. */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const { prefs, update, loggedIn, ready } = usePreferences();
  const { user } = useAuth();
  const ownerId = useRef<number>(0);
  ownerId.current = user?.id ?? 0;
  const [temp, setTemp] = useState<Theme>(readTemp);
  const theme: Theme = loggedIn ? asTheme(prefs.theme) : temp;
  const customColors = useMemo(() => validColors(prefs.custom_colors) ?? DEFAULT_CUSTOM, [prefs.custom_colors]);
  const colors = useMemo(() => themeColors(theme, prefs.custom_colors), [theme, prefs.custom_colors]);
  const palette = useMemo(() => (colors ? derivePalette(colors) : null), [colors]);
  const [resolved, setResolved] = useState<"light" | "dark">(() => (document.documentElement.classList.contains("dark") ? "dark" : "light"));

  useEffect(() => {
    if (!ready) return;                                      // until we know who is signed in, keep what the init script set
    const root = document.documentElement;
    for (const name of ALL_VARS) root.style.removeProperty(name);   // including any the init script applied from the device copy
    if (palette) {
      // Through the style API, not a style attribute in markup: the Content-Security-Policy allows this.
      for (const [name, value] of Object.entries(palette.vars)) { root.style.setProperty(name, value); }
      setResolved(palette.base);
      root.classList.toggle("dark", palette.base === "dark");
      if (ownerId.current) writeCopy(ownerId.current, { vars: palette.vars, base: palette.base });
      return;
    }
    const apply = () => {
      const r = resolveTheme(theme);
      setResolved(r);
      root.classList.toggle("dark", r === "dark");
    };
    apply();
    if (ownerId.current) writeCopy(ownerId.current, { vars: null, base: null });
    if (theme !== "system" || typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", apply);                      // follow the OS while on "System"
    return () => mq.removeEventListener("change", apply);
  }, [theme, palette, ready]);

  const setTheme = useCallback((t: Theme) => {
    if (loggedIn) { void update({ theme: t }); return; }
    const b = asBuiltIn(t);
    setTemp(b);
    try { sessionStorage.setItem(TEMP_THEME_KEY, b); } catch { /* applies for this visit only */ }
  }, [loggedIn, update]);
  const setCustomColors = useCallback((c: Colors) => { void update({ theme: "custom", custom_colors: c }); }, [update]);

  const value = useMemo(() => ({ theme, resolved, setTheme, colors, palette, customColors, setCustomColors }),
    [theme, resolved, setTheme, colors, palette, customColors, setCustomColors]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useTheme(): Value {
  const v = useContext(Ctx);
  if (!v) throw new Error("useTheme must be used inside <ThemeProvider>");
  return v;
}
