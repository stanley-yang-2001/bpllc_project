import { Flame } from "lucide-react";
import { Link } from "react-router-dom";
import { useI18n } from "../i18n/I18nProvider";
import { useRewards } from "./useRewards";

/** A small always-visible streak and goal in the top bar, a link to the progress page. Nothing when rewards are off or not loaded. */
export function StreakChip() {
  const { t } = useI18n();
  const { data } = useRewards();
  if (!data || !data.show_rewards) return null;
  const { streak, goal } = data;
  const text = `${t("practice.progress.streak", { n: streak.days })}, ${t("rewards.goal.progress", { done: goal.done, target: goal.target })}`;
  return (
    <Link to="/progress" aria-label={`${t("rewards.chip.label")}: ${text}`} title={text}
      className={`flex items-center gap-1 rounded-lg border px-2 py-1 text-sm font-medium transition hover:bg-slate-100 ${streak.practised_today ? "border-emerald-300 text-emerald-800 dark:text-emerald-300" : "border-slate-300 text-slate-700"}`}>
      <Flame aria-hidden className={`size-4 ${streak.alive ? "text-amber-600 dark:text-amber-300" : "text-slate-400"}`} />
      <span>{streak.days}</span>
      <span aria-hidden className="hidden text-xs font-normal text-slate-500 sm:inline">· {goal.done}/{goal.target}</span>
    </Link>
  );
}
