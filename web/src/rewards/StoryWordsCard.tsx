import { BookOpenCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { useI18n } from "../i18n/I18nProvider";
import { Card } from "../components/ui";

/** How many of the learner's words have turned up in a story they saved. Hidden until they have words. */
export function StoryWordsCard({ used, total }: { used: number; total: number }) {
  const { t } = useI18n();
  if (total === 0) return null;
  const title = t("rewards.storywords.title");
  return (
    <Card className="mb-8">
      <section data-testid="storywords-card" aria-label={title}>
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-500"><BookOpenCheck aria-hidden className="size-4" />{title}</h2>
        <p className="mt-1 text-slate-800">{t("rewards.storywords.line", { used, total })}</p>
        <div role="progressbar" aria-label={title} aria-valuemin={0} aria-valuemax={total} aria-valuenow={used} className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200">
          <div className="h-full rounded-full bg-emerald-600" style={{ width: `${Math.round((used / total) * 100)}%` }} />
        </div>
        {used < total && <p className="mt-2 text-xs text-slate-600">{t("rewards.storywords.hint")} <Link to="/studio" className="font-medium text-brand-700 hover:underline dark:text-brand-200">Story Studio</Link></p>}
      </section>
    </Card>
  );
}
