import { Monitor, Moon, Palette, Sun } from "lucide-react";
import { useState } from "react";
import { Badge, Button, inputCls } from "../components/ui";
import { useI18n } from "../i18n/I18nProvider";
import type { MessageKey } from "../i18n/messages";
import { usePreferences } from "../prefs/PreferencesProvider";
import { ColorWheel } from "../theme/ColorWheel";
import { contrast } from "../theme/color";
import { DEFAULT_CUSTOM, derivePalette, PARTS, PRESET_IDS, PRESETS, type Colors, type PresetId } from "../theme/palette";
import { useTheme, type Theme } from "../theme/ThemeProvider";
import { Section } from "./Section";

const BUILT_INS: { value: Theme; label: MessageKey; icon: typeof Sun }[] = [
  { value: "light", label: "settings.appearance.light", icon: Sun },
  { value: "dark", label: "settings.appearance.dark", icon: Moon },
  { value: "system", label: "settings.appearance.system", icon: Monitor },
];
const PRESET_LABEL: Record<PresetId, MessageKey> = {
  ocean: "theme.preset.ocean", forest: "theme.preset.forest", sunset: "theme.preset.sunset", rose: "theme.preset.rose",
  midnight: "theme.preset.midnight", graphite: "theme.preset.graphite", contrast: "theme.preset.contrast",
};
const PART_LABEL: Record<(typeof PARTS)[number], MessageKey> = {
  page: "settings.custom.page", cards: "settings.custom.cards", text: "settings.custom.text",
  borders: "settings.custom.borders", accent: "settings.custom.accent",
};
/** The built-in Light and Dark as five colours, so "Start from" can offer them too. */
const LIGHT_COLORS: Colors = { page: "#f8fafc", cards: "#ffffff", text: "#0f172a", borders: "#e2e8f0", accent: "#4f46e5" };
const DARK_COLORS: Colors = { page: "#020617", cards: "#0f172a", text: "#f8fafc", borders: "#2a374d", accent: "#4f46e5" };

/** A tile: a radio with a small preview of the theme's page, card, accent and text colours. */
function Tile({ value, label, current, onPick, preview, icon: Icon }: {
  value: Theme; label: string; current: Theme; onPick: () => void; preview?: Colors; icon?: typeof Sun;
}) {
  const on = current === value;
  return (
    <label className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm transition has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-brand-500 ${
      on ? "border-brand-500 bg-surface font-medium text-slate-900 shadow-xs" : "border-slate-200 text-slate-600 hover:border-slate-300 hover:text-slate-900"
    }`}>
      <input type="radio" name="theme" value={value} checked={on} onChange={onPick} className="sr-only" />
      {preview ? (
        <span aria-hidden className="flex size-6 shrink-0 overflow-hidden rounded-md border border-slate-300" style={{ background: preview.page }}>
          <span className="m-auto size-3 rounded-sm" style={{ background: preview.cards, boxShadow: `inset 0 -3px 0 ${preview.accent}`, border: `1px solid ${preview.borders}` }} />
        </span>
      ) : Icon ? <Icon aria-hidden className="size-4 shrink-0" /> : null}
      {label}
    </label>
  );
}

function ratioLine(label: string, ratio: number, t: (k: MessageKey) => string) {
  const good = ratio >= 4.5;
  return (
    <li key={label} className="flex items-center justify-between gap-3">
      <span>{label}</span>
      <span className="flex items-center gap-2">
        <span className="tabular-nums">{ratio.toFixed(1)}:1</span>
        <Badge tone={good ? "good" : "bad"}>{good ? t("settings.custom.good") : t("settings.custom.hard")}</Badge>
      </span>
    </li>
  );
}

function CustomEditor() {
  const { customColors, setCustomColors, palette, theme } = useTheme();
  const { t } = useI18n();
  const [part, setPart] = useState<(typeof PARTS)[number]>("page");
  const colors = customColors;
  const shown = theme === "custom" ? palette : derivePalette(colors);
  const accentUsed = shown?.vars["--color-brand-600"] ?? colors.accent;
  const partName = t(PART_LABEL[part]);
  const starts: { id: string; label: string; colors: Colors }[] = [
    { id: "light", label: t("settings.appearance.light"), colors: LIGHT_COLORS },
    { id: "dark", label: t("settings.appearance.dark"), colors: DARK_COLORS },
    ...PRESET_IDS.map((id) => ({ id, label: t(PRESET_LABEL[id]), colors: PRESETS[id].colors as Colors })),
  ];
  return (
    <div className="mt-5 border-t border-slate-200 pt-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-medium text-slate-900">{t("settings.custom.title")}</h3>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          {t("settings.custom.startFrom")}
          <select className={`${inputCls} w-auto`} value="" onChange={(e) => { const s = starts.find((x) => x.id === e.target.value); if (s) setCustomColors(s.colors); }}>
            <option value="" />
            {starts.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
        </label>
      </div>
      <fieldset className="mt-4">
        <legend className="mb-2 text-sm font-medium text-slate-700">{t("settings.custom.part")}</legend>
        <div className="flex flex-wrap gap-2">
          {PARTS.map((p) => (
            <label key={p} className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-1.5 text-sm has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-brand-500 ${part === p ? "border-brand-500 bg-surface font-medium text-slate-900" : "border-slate-200 text-slate-600"}`}>
              <input type="radio" name="custom-part" className="sr-only" checked={part === p} onChange={() => setPart(p)} />
              <span aria-hidden className="size-3.5 rounded-full border border-slate-400" style={{ background: colors[p] }} />
              {t(PART_LABEL[p])}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="mt-4">
        <ColorWheel
          value={colors[part]}
          onChange={(hex) => setCustomColors({ ...colors, [part]: hex })}
          label={t("settings.custom.wheel", { part: partName })}
          brightnessLabel={t("settings.custom.brightness")}
          hexLabel={t("settings.custom.hex")}
          spoken={(h, s) => t("settings.custom.wheelSpoken", { hue: Math.round(h), strength: Math.round(s * 100) })}
        />
      </div>
      <div className="mt-5">
        <h4 className="text-sm font-medium text-slate-900">{t("settings.custom.readability")}</h4>
        <ul className="mt-2 max-w-sm space-y-1.5 text-sm text-slate-700">
          {ratioLine(t("settings.custom.textOnPage"), contrast(colors.text, colors.page), t)}
          {ratioLine(t("settings.custom.textOnCards"), contrast(colors.text, colors.cards), t)}
          {ratioLine(t("settings.custom.buttonText"), contrast("#ffffff", accentUsed), t)}
        </ul>
        {shown?.accentDarkened && <p className="mt-2 text-xs text-slate-600">{t("settings.custom.darkened")}</p>}
        <Button variant="secondary" className="mt-3" onClick={() => setCustomColors(DEFAULT_CUSTOM)}>{t("settings.custom.reset")}</Button>
      </div>
    </div>
  );
}

export function AppearanceSection() {
  const { theme, setTheme } = useTheme();
  const { saveFailed, loggedIn } = usePreferences();
  const { t } = useI18n();
  return (
    <Section title={t("settings.appearance.title")} description={t("settings.appearance.description")}>
      <div role="radiogroup" aria-label={t("settings.appearance.theme")} className="flex flex-wrap gap-2">
        {BUILT_INS.map(({ value, label, icon }) => <Tile key={value} value={value} label={t(label)} current={theme} icon={icon} onPick={() => setTheme(value)} />)}
        {PRESET_IDS.map((id) => <Tile key={id} value={id} label={t(PRESET_LABEL[id])} current={theme} preview={PRESETS[id].colors} onPick={() => setTheme(id)} />)}
        <Tile value="custom" label={t("theme.custom")} current={theme} onPick={() => setTheme("custom")} icon={Palette} />
      </div>
      {loggedIn && theme === "custom" && <CustomEditor />}
      {saveFailed && (
        <p role="status" className="mt-3 text-sm text-amber-800 dark:text-amber-200">
          {t("settings.appearance.saveFailed")}
        </p>
      )}
    </Section>
  );
}
