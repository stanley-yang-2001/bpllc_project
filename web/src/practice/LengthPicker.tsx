import { useState } from "react";
import { useI18n } from "../i18n/I18nProvider";

export const PRESET_SECONDS = [120, 300, 600, 1200, 1800];
export const MIN_SECONDS = 10;
const MAX_MINUTES = 180;

const chipClass = (on: boolean) => `rounded-full border px-3 py-1 text-sm ${on ? "border-brand-600 bg-brand-600 text-white" : "border-slate-300 bg-surface text-slate-700 hover:bg-slate-100/70"}`;

/** How long a flashcard session lasts: a few ready choices, no limit, or a length of the learner's own in minutes and seconds.
 * `value` is in seconds (null = no limit). A custom length is at least 10 seconds. */
export function LengthPicker({ value, onChange }: { value: number | null; onChange: (seconds: number | null) => void }) {
  const { t } = useI18n();
  const [custom, setCustom] = useState(value !== null && !PRESET_SECONDS.includes(value));
  const [min, setMin] = useState(value !== null && !PRESET_SECONDS.includes(value) ? Math.floor(value / 60) : 1);
  const [sec, setSec] = useState(value !== null && !PRESET_SECONDS.includes(value) ? value % 60 : 30);
  const apply = (m: number, s: number) => onChange(Math.max(MIN_SECONDS, m * 60 + s));
  const clamp = (raw: string, max: number) => Math.min(max, Math.max(0, Math.floor(Number(raw) || 0)));
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label={t("practice.cards.length")}>
        <span className="text-sm text-slate-700">{t("practice.cards.length")}</span>
        {PRESET_SECONDS.map((s) => (
          <button key={s} type="button" aria-pressed={!custom && value === s} onClick={() => { setCustom(false); onChange(s); }} className={chipClass(!custom && value === s)}>
            {t("practice.stats.minutes", { n: s / 60 })}
          </button>
        ))}
        <button type="button" aria-pressed={custom} onClick={() => { setCustom(true); apply(min, sec); }} className={chipClass(custom)}>{t("practice.cards.custom")}</button>
        <button type="button" aria-pressed={!custom && value === null} onClick={() => { setCustom(false); onChange(null); }} className={chipClass(!custom && value === null)}>{t("practice.cards.noLimit")}</button>
      </div>
      {custom && (
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-1.5 text-sm text-slate-700">
            <input type="number" inputMode="numeric" min={0} max={MAX_MINUTES} value={min} aria-label={t("practice.cards.minutes")}
              onChange={(e) => { const m = clamp(e.target.value, MAX_MINUTES); setMin(m); apply(m, sec); }}
              className="w-20 rounded-md border border-slate-300 bg-surface px-2 py-1" />
            {t("practice.cards.minutes")}
          </label>
          <label className="flex items-center gap-1.5 text-sm text-slate-700">
            <input type="number" inputMode="numeric" min={0} max={59} value={sec} aria-label={t("practice.cards.seconds")}
              onChange={(e) => { const s = clamp(e.target.value, 59); setSec(s); apply(min, s); }}
              className="w-20 rounded-md border border-slate-300 bg-surface px-2 py-1" />
            {t("practice.cards.seconds")}
          </label>
        </div>
      )}
    </div>
  );
}
