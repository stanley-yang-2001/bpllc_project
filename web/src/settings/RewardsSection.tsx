import { useI18n } from "../i18n/I18nProvider";
import { usePreferences } from "../prefs/PreferencesProvider";
import { inputCls } from "../components/ui";
import { Label, Section } from "./Section";

const GOALS = [5, 10, 15, 20, 30, 50, 100];

export function RewardsSection() {
  const { prefs, update } = usePreferences();
  const { t } = useI18n();
  const goals = GOALS.includes(prefs.daily_goal) ? GOALS : [...GOALS, prefs.daily_goal].sort((a, b) => a - b);
  return (
    <Section title={t("rewards.settings.title")} description={t("rewards.settings.description")}>
      <Label htmlFor="daily-goal">{t("rewards.settings.goal")}</Label>
      <select id="daily-goal" className={`${inputCls} max-w-40`} value={prefs.daily_goal} onChange={(e) => void update({ daily_goal: Number(e.target.value) })}>
        {goals.map((n) => <option key={n} value={n}>{n}</option>)}
      </select>
      <label className="mt-4 flex cursor-pointer items-start gap-2.5 text-sm text-slate-800">
        <input type="checkbox" className="mt-0.5 size-4 rounded accent-brand-600" checked={prefs.show_rewards} onChange={(e) => void update({ show_rewards: e.target.checked })} />
        {t("rewards.settings.show")}
      </label>
    </Section>
  );
}
