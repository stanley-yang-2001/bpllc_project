import { contrast, luminance, mix, normalizeHex } from "./color";

/** The five parts a learner can colour (design 3G). */
export interface Colors { page: string; cards: string; text: string; borders: string; accent: string }
export const PARTS = ["page", "cards", "text", "borders", "accent"] as const satisfies readonly (keyof Colors)[];

export interface Palette {
  vars: Record<string, string>;         // CSS custom properties to set on <html>
  base: "light" | "dark";               // whether `.dark` is on
  accentDarkened: boolean;              // the accent had to be darkened so white button text stays readable
}

const WHITE = "#ffffff", BLACK = "#000000";
/** The furthest a tone can move from `from` toward `to` while still reaching `ratio` against every colour in `against`. */
function farthest(from: string, to: string, against: string[], ratio: number): string {
  let best = from;                                          // if even `from` fails, `from` is the best we can do
  for (let i = 0; i <= 100; i++) {
    const c = mix(from, to, i / 100);
    if (against.every((a) => contrast(c, a) >= ratio)) best = c; else if (i > 0 && best !== from) break;
  }
  return best;
}

/** Every token from five picks. Pure: the same picks always give the same map. */
export function derivePalette(colors: Colors): Palette {
  const { page, cards, text, borders } = colors;
  const base: "light" | "dark" = luminance(page) < 0.18 ? "dark" : "light";
  let accent = colors.accent;
  let accentDarkened = false;
  const picked = colors.accent;
  // White text must read on the accent (buttons). On a light base the accent is also link text on the page and the
  // cards, so it must read there too; on a dark base links use the light end of the scale instead.
  const readable = (a: string) => contrast(a, WHITE) >= 4.5 && (base === "dark" || (contrast(a, page) >= 4.5 && contrast(a, cards) >= 4.5));
  // Darken in fixed steps toward black. It stops at black (or when nothing darker helps), so it always ends.
  for (let i = 1; i <= 50 && !readable(accent); i++) { accent = mix(picked, BLACK, i * 0.02); accentDarkened = true; }

  const subtle = mix(page, borders, 0.5);                   // slate-100
  const hint = farthest(text, page, [page, cards, subtle], 4.6);
  const desc = farthest(text, page, [page, cards], 7);
  const vars: Record<string, string> = {
    "--color-surface": cards,
    "--color-slate-50": page,
    "--color-slate-100": subtle,
    "--color-slate-200": borders,
    "--color-slate-300": mix(borders, text, 0.25),
    "--color-slate-400": mix(hint, borders, 0.4),
    "--color-slate-500": hint,
    "--color-slate-600": desc,
    "--color-slate-700": mix(text, desc, 0.45),
    "--color-slate-800": mix(text, desc, 0.2),
    "--color-slate-900": text,
    "--color-brand-50": mix(accent, WHITE, 0.92),
    "--color-brand-100": mix(accent, WHITE, 0.85),
    "--color-brand-200": mix(accent, WHITE, 0.7),
    "--color-brand-500": mix(accent, WHITE, 0.15),
    "--color-brand-600": accent,
    "--color-brand-700": mix(accent, BLACK, 0.15),
    "--color-brand-800": mix(accent, BLACK, 0.3),
    "--color-brand-900": mix(accent, BLACK, 0.42),
  };
  return { vars, base, accentDarkened };
}

export const PRESETS = {
  ocean:    { label: "Ocean",         colors: { page: "#eef6ff", cards: "#ffffff", text: "#0b2540", borders: "#c9dcf0", accent: "#0369a1" } },
  forest:   { label: "Forest",        colors: { page: "#f1f7f0", cards: "#ffffff", text: "#14301c", borders: "#cfe2cc", accent: "#15803d" } },
  sunset:   { label: "Sunset",        colors: { page: "#fff6ec", cards: "#fffdf9", text: "#3b1d0e", borders: "#f0d8c0", accent: "#c2410c" } },
  rose:     { label: "Rose",          colors: { page: "#fff0f4", cards: "#ffffff", text: "#4a1424", borders: "#f4cbd8", accent: "#be123c" } },
  midnight: { label: "Midnight",      colors: { page: "#070b1a", cards: "#0e1530", text: "#e8ecff", borders: "#222c52", accent: "#4f46e5" } },
  graphite: { label: "Graphite",      colors: { page: "#101010", cards: "#1a1a1a", text: "#f2f2f2", borders: "#2e2e2e", accent: "#2563eb" } },
  contrast: { label: "High contrast", colors: { page: "#ffffff", cards: "#ffffff", text: "#000000", borders: "#000000", accent: "#0000b3" } },
} as const satisfies Record<string, { label: string; colors: Colors }>;
export type PresetId = keyof typeof PRESETS;
export const PRESET_IDS = Object.keys(PRESETS) as PresetId[];
export const isPreset = (id: unknown): id is PresetId => typeof id === "string" && Object.prototype.hasOwnProperty.call(PRESETS, id);

/** What a custom theme starts as when the learner has never picked colours. */
export const DEFAULT_CUSTOM: Colors = PRESETS.ocean.colors;

/** Colours from the account, if all five are valid hex; anything else is ignored. */
export function validColors(v: unknown): Colors | null {
  if (!v || typeof v !== "object") return null;
  const out: Record<string, string> = {};
  for (const k of PARTS) {
    const h = typeof (v as Record<string, unknown>)[k] === "string" ? normalizeHex((v as Record<string, string>)[k]) : null;
    if (!h) return null;
    out[k] = h;
  }
  return out as unknown as Colors;
}
