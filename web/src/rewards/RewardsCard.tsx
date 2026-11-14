import { Award, ArrowRight, Flame } from "lucide-react";
import { Link } from "react-router-dom";
import { useI18n } from "../i18n/I18nProvider";
import { Card, Skeleton } from "../components/ui";
import { badgeText } from "./badgeText";
import { GoalRing } from "./GoalRing";
import { useRewards } from "./useRewards";

/** The progress card at the top of Home: today's goal, the streak, the week in one line and the next badge. Hidden when the learner turned rewards off. */
export function RewardsCard() {
  const { t } = useI18n();
  const q = useRewards();
  if (q.isError || (q.data && !q.data.show_rewards)) return null;
  if (!q.data) return <Card className="mb-8"><Skeleton className="h-20 w-full" /></Card>;
  const { streak, goal, week, next_badge: next } = q.data;
  const message = streak.practised_today ? t("rewards.streak.done") : streak.alive ? t("rewards.streak.keep") : t("rewards.streak.start");
  const nextText = next ? badgeText(next.id, next.target, t) : null;
  return (
    <Card className="mb-8">
      <section data-testid="rewards-card" aria-label={t("rewards.title")}>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-4">
          <div className="flex items-center gap-4">
            <GoalRing done={goal.done} target={goal.target} label={t("rewards.goal.title")} valueText={t("rewards.goal.progress", { done: goal.done, target: goal.target })} />
            <div>
              <p className="text-sm font-medium text-slate-600">{t("rewards.goal.title")}</p>
              <p className="font-semibold text-slate-900">{t("rewards.goal.progress", { done: goal.done, target: goal.target })}</p>
              <p className={`text-sm ${goal.reached ? "text-emerald-800 dark:text-emerald-300" : "text-slate-600"}`}>
                {goal.reached ? t("rewards.goal.reached") : t("rewards.goal.left", { n: goal.left })}
              </p>
            </div>
          </div>

          <div className="min-w-48 flex-1">
            <p className="flex items-center gap-2 text-lg font-semibold text-slate-900">
              <Flame aria-hidden className={`size-6 ${streak.alive ? "text-amber-600 dark:text-amber-300" : "text-slate-400"}`} />
              {t("practice.progress.streak", { n: streak.days })}
              {streak.best > streak.days && <span className="text-sm font-normal text-slate-500">· {t("rewards.streak.best", { n: streak.best })}</span>}
            </p>
            <p className="text-sm text-slate-700">{message}</p>
            {streak.alive && streak.days > 0 && (
              <p className="mt-0.5 text-xs text-slate-600">{streak.rest_available ? t("rewards.streak.rest") : streak.rest_used_on ? t("rewards.streak.restUsed") : null}</p>
            )}
          </div>

          <Link to="/practice" className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white shadow-xs transition hover:bg-brand-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600">
            {t("rewards.practice")}
          </Link>
        </div>

        <dl className="mt-5 grid grid-cols-2 gap-3 border-t border-slate-200 pt-4 text-sm sm:grid-cols-4">
          {([["rewards.week.days", `${week.days_practised}/7`], ["rewards.week.learned", week.words_learned], ["rewards.week.stories", week.stories_saved], ["rewards.week.due", week.due_now]] as const).map(([key, value]) => (
            <div key={key}>
              <dt className="text-slate-600">{t(key)}</dt>
              <dd className="text-xl font-semibold text-slate-900">{value}</dd>
            </div>
          ))}
        </dl>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm">
          {next && nextText ? (
            <div className="min-w-56 flex-1">
              <p className="flex items-center gap-1.5 text-slate-700"><Award aria-hidden className="size-4 text-brand-600" /><span className="font-medium">{t("rewards.next.title")}:</span> {nextText.name} <span className="text-slate-500">({t("rewards.badge.progress", { have: next.have, target: next.target })})</span></p>
              <div role="progressbar" aria-label={nextText.name} aria-valuemin={0} aria-valuemax={next.target} aria-valuenow={next.have} className="mt-1.5 h-2 overflow-hidden rounded-full bg-slate-200">
                <div className="h-full rounded-full bg-brand-600" style={{ width: `${Math.round((next.have / next.target) * 100)}%` }} />
              </div>
              <p className="mt-1 text-xs text-slate-600">{nextText.how}</p>
            </div>
          ) : <span />}
          <Link to="/progress" className="inline-flex items-center gap-1 font-medium text-brand-700 hover:underline dark:text-brand-200">
            {t("rewards.badges.all")} <ArrowRight aria-hidden className="size-4" />
          </Link>
        </div>
      </section>
    </Card>
  );
}
