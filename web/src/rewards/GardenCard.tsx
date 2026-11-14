import { Circle, Sprout, TreeDeciduous } from "lucide-react";
import type { Garden } from "./garden";
import { useI18n } from "../i18n/I18nProvider";
import { Card } from "../components/ui";
import { gardenPlots } from "./garden";

/** The learner's words as a garden: a seed for each word not practised yet, a sprout for each being learned, a tree for each Known word. */
export function GardenCard({ garden }: { garden: Garden }) {
  const { t } = useI18n();
  const title = t("rewards.garden.title");
  const total = garden.seeds + garden.sprouts + garden.trees;
  const plots = gardenPlots(garden);
  const rows = [["trees", garden.trees, TreeDeciduous, "text-emerald-700 dark:text-emerald-400"], ["sprouts", garden.sprouts, Sprout, "text-lime-700 dark:text-lime-400"], ["seeds", garden.seeds, Circle, "text-amber-700 dark:text-amber-400"]] as const;
  return (
    <Card className="mb-8">
      <section data-testid="garden-card" aria-label={title}>
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-500"><Sprout aria-hidden className="size-4" />{title}</h2>
        {total === 0 ? <p className="mt-1 text-sm text-slate-600">{t("rewards.garden.empty")}</p> : (
          <>
            <p className="mt-1 text-sm text-slate-600">{t("rewards.garden.note")}</p>
            <div aria-hidden className="mt-3 flex flex-wrap gap-1.5" data-testid="garden-plots">
              {plots.map((p, i) => {
                const [, , Icon, colour] = rows.find((r) => r[0] === p)!;
                return <Icon key={i} className={`${p === "trees" ? "size-6" : p === "sprouts" ? "size-5" : "size-3.5"} ${colour}`} />;
              })}
            </div>
            <dl className="mt-3 grid grid-cols-3 gap-3 text-sm">
              {rows.map(([key, n, Icon, colour]) => (
                <div key={key}><dt className="flex items-center gap-1.5 text-slate-600"><Icon aria-hidden className={`size-4 ${colour}`} />{t(`rewards.garden.${key}`)}</dt><dd className="text-xl font-semibold text-slate-900">{n}</dd></div>
              ))}
            </dl>
          </>
        )}
      </section>
    </Card>
  );
}
