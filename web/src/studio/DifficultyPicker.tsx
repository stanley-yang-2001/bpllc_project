import { useI18n } from "../i18n/I18nProvider";
import { inputCls } from "../components/ui";
import type { Difficulty, Tier } from "./useDifficulty";

const KEYS = [["length", "studio.diffLength"], ["own_words", "studio.diffOwn"], ["uncommon_pct", "studio.diffUncommon"]] as const;

export function DifficultyPicker({ d }: { d: Difficulty }) {
  const { t } = useI18n();
  const preset = d.tier !== "" && d.tier !== "custom" ? d.options?.presets[d.tier] : undefined;
  const limits = d.options?.limits;
  return (
    <div>
      <label htmlFor="story-difficulty" className="mb-1 block text-sm font-medium text-slate-700">{t("studio.difficulty")}</label>
      <select id="story-difficulty" className={`${inputCls} sm:max-w-xs`} value={d.tier} onChange={(e) => d.setTier(e.target.value as Tier)}>
        <option value="">{t("studio.diffAny")}</option>
        <option value="easy">{t("studio.diffEasy")}</option>
        <option value="medium">{t("studio.diffMedium")}</option>
        <option value="hard">{t("studio.diffHard")}</option>
        <option value="custom">{t("studio.diffCustom")}</option>
      </select>
      {preset && <p className="mt-1 text-xs text-slate-600">{t("studio.diffPreset", { length: preset.length, own: preset.own_words, pct: preset.uncommon_pct })}</p>}
      {d.tier === "custom" && limits && (
        <div className="mt-2 grid gap-3 sm:grid-cols-3">
          {KEYS.map(([key, label]) => (
            <div key={key}>
              <label htmlFor={`diff-${key}`} className="mb-1 block text-sm font-medium text-slate-700">{t(label)}</label>
              <input
                id={`diff-${key}`} type="number" inputMode="numeric" className={inputCls} value={d.nums[key]}
                min={limits[key][0]} max={limits[key][1]} step={1}
                onChange={(e) => d.setNums({ ...d.nums, [key]: e.target.value })}
                aria-invalid={d.picked[key] === null}
              />
            </div>
          ))}
          <p className={`text-xs sm:col-span-3 ${d.bad ? "text-red-700" : "text-slate-600"}`}>
            {d.bad && <>{t("studio.diffBad")} </>}
            {t("studio.diffLimits", { lmin: limits.length[0], lmax: limits.length[1], omin: limits.own_words[0], omax: limits.own_words[1], umin: limits.uncommon_pct[0], umax: limits.uncommon_pct[1] })}
          </p>
        </div>
      )}
      {d.tier !== "" && <p className="mt-1 text-xs text-slate-600">{t("studio.diffNote")}</p>}
    </div>
  );
}
