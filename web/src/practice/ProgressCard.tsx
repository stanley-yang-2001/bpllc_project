import { useQuery } from "@tanstack/react-query";
import { Flame } from "lucide-react";
import { api } from "../api/client";
import { progressKey } from "../api/keys";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n/I18nProvider";
import { Button, Card, Skeleton } from "../components/ui";

/** How the learner is doing in this language: what is due, what is new, what is known, and the day streak.
 * A failed load just hides the card: practice works without it. */
export function ProgressCard({ language, onReview }: { language: string; onReview: () => void }) {
  const { user } = useAuth();
  const { t } = useI18n();
  const q = useQuery({ queryKey: progressKey(user!.id, language), queryFn: () => api.practiceProgress(language) });
  if (q.isPending) return <Skeleton className="mb-4 h-24 w-full" />;
  if (q.isError) return null;
  const p = q.data;
  if (p.new + p.learning + p.known === 0) return null;                // no words with a meaning yet: nothing to report
  const ready = p.due + p.new;
  const stats: [string, number][] = [[t("practice.progress.due"), p.due], [t("practice.progress.new"), p.new], [t("practice.progress.learning"), p.learning], [t("practice.progress.known"), p.known]];
  return (
    <Card className="mb-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold text-slate-900">{t("practice.progress.title")}</h2>
        {p.streak > 0 && <span className="flex items-center gap-1 text-sm font-medium text-slate-700"><Flame aria-hidden className="size-4" />{t("practice.progress.streak", { n: p.streak })}</span>}
      </div>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {stats.map(([label, n]) => (
          <div key={label}><dt className="text-xs text-slate-600">{label}</dt><dd className="text-2xl font-semibold text-slate-900">{n}</dd></div>
        ))}
      </dl>
      {ready > 0 ? <Button onClick={onReview}>{t("practice.progress.review")}</Button> : <p className="text-sm text-slate-600">{t("practice.progress.nothingDue")}</p>}
    </Card>
  );
}
