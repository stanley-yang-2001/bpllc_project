import { useQuery } from "@tanstack/react-query";
import { api, type SetFilter } from "../api/client";
import type { HardWord } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n/I18nProvider";
import { Button, Card, Skeleton } from "../components/ui";
import { formatMs } from "./session";

const STAGES = [
  ["new", "bg-slate-400"], ["learning", "bg-amber-500"], ["relearning", "bg-red-500"], ["young", "bg-sky-500"], ["mature", "bg-emerald-600"],
] as const;
const pct = (x: number | null | undefined) => (x === null || x === undefined ? "–" : `${Math.round(x * 100)}%`);

/** How memory is going for the chosen sets (from the learner's own answers) and which words are hardest. A failed load hides the
 * panel: studying works without it. */
export function StudyStats({ language, set, onPractise }: { language: string; set: SetFilter; onPractise: (ids: number[]) => void }) {
  const { user } = useAuth();
  const { t, locale } = useI18n();
  const stats = useQuery({ queryKey: ["practice", user!.id, "stats", language, String(set)], queryFn: () => api.studyStats(language, set) });
  const hard = useQuery({ queryKey: ["practice", user!.id, "hardest", language, String(set)], queryFn: () => api.hardestWords(language, set, 8) });
  if (stats.isPending) return <Skeleton className="mb-4 h-32 w-full" />;
  if (stats.isError || stats.data.words === 0) return null;
  const s = stats.data;
  const total = Math.max(1, s.words);
  const maxDue = Math.max(1, ...s.forecast.map((d) => d.due));
  const day = (iso: string) => new Date(`${iso}T00:00:00Z`).toLocaleDateString(locale, { weekday: "short", timeZone: "UTC" });
  const tiles: [string, string][] = s.reviews_30d === 0 ? [] : [
    [t("practice.stats.retention"), pct(s.retention_30d)], [t("practice.stats.accuracy"), pct(s.accuracy_30d)],
    [t("practice.stats.avgTime"), s.avg_think_ms === null || s.avg_think_ms === undefined ? "–" : formatMs(s.avg_think_ms)],
    [t("practice.stats.studied"), t("practice.stats.minutes", { n: Math.max(1, Math.round(s.studied_seconds_30d / 60)) })],
    [t("practice.stats.today"), String(s.today_reviews)],
  ];
  const counts: Record<string, number> = { new: s.new, learning: s.learning, relearning: s.relearning, young: s.young, mature: s.mature };
  return (
    <Card className="mb-4 space-y-5">
      <h2 className="font-semibold text-slate-900">{t("practice.stats.title")}</h2>
      {tiles.length === 0 ? <p className="text-sm text-slate-600">{t("practice.stats.none")}</p> : (
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {tiles.map(([label, value]) => <div key={label}><dt className="text-xs text-slate-600">{label}</dt><dd className="text-xl font-semibold text-slate-900">{value}</dd></div>)}
        </dl>
      )}
      <div>
        <h3 className="mb-1 text-sm font-medium text-slate-700">{t("practice.stats.stages")}</h3>
        <div className="flex h-3 overflow-hidden rounded-full bg-slate-100" aria-hidden>
          {STAGES.map(([k, cls]) => counts[k] > 0 && <div key={k} className={cls} style={{ width: `${(counts[k] / total) * 100}%` }} />)}
        </div>
        <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-700">
          {STAGES.map(([k, cls]) => <li key={k} className="flex items-center gap-1"><span aria-hidden className={`inline-block size-2.5 rounded-full ${cls}`} />{t(`practice.cards.status.${k}`)} {counts[k]}</li>)}
        </ul>
        {s.leeches > 0 && <p className="mt-1 text-xs text-slate-600">{t("practice.stats.leeches", { n: s.leeches })}</p>}
      </div>
      <div>
        <h3 className="mb-1 text-sm font-medium text-slate-700">{t("practice.stats.forecast")}</h3>
        <ol className="grid grid-cols-7 items-end gap-1.5 text-center">
          {s.forecast.map((d) => (
            <li key={d.day} className="flex flex-col items-center gap-1" aria-label={`${day(d.day)}: ${d.due}`}>
              <span className="text-xs text-slate-800">{d.due}</span>
              <span className="w-full rounded-sm bg-brand-600/70" style={{ height: `${Math.max(2, (d.due / maxDue) * 48)}px` }} />
              <span className="text-xs text-slate-600">{day(d.day)}</span>
            </li>
          ))}
        </ol>
      </div>
      <Hardest words={hard.data?.items ?? []} loading={hard.isPending} language={language} onPractise={onPractise} />
    </Card>
  );
}

function Hardest({ words, loading, language, onPractise }: { words: HardWord[]; loading: boolean; language: string; onPractise: (ids: number[]) => void }) {
  const { t } = useI18n();
  if (loading) return <Skeleton className="h-20 w-full" />;
  return (
    <div>
      <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-slate-700">{t("practice.hard.title")}</h3>
        {words.length > 0 && <Button variant="secondary" onClick={() => onPractise(words.map((w) => w.id))}>{t("practice.hard.practise")}</Button>}
      </div>
      {words.length === 0 ? <p className="text-sm text-slate-600">{t("practice.hard.none")}</p> : (
        <ol className="divide-y divide-slate-200">
          {words.map((w) => (
            <li key={w.id} className="py-2">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p><span lang={language} className="font-medium text-slate-900">{w.word}</span>{w.meaning && <span className="ml-2 text-sm text-slate-700">{w.meaning}</span>}</p>
                <span className="text-xs text-slate-600" aria-label={String(w.score)}>{w.score}/100</span>
              </div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100" aria-hidden><div className="h-full bg-red-500/80" style={{ width: `${w.score}%` }} /></div>
              <p className="mt-1 text-xs text-slate-600">
                {w.avg_think_ms === null || w.avg_think_ms === undefined
                  ? t("practice.hard.noTime", { n: w.reviews, miss: Math.round(w.miss_rate * 100) })
                  : t("practice.hard.detail", { n: w.reviews, miss: Math.round(w.miss_rate * 100), time: formatMs(w.avg_think_ms) })}
                {w.reasons.length > 0 && <> · {w.reasons.map((r) => t(`practice.hard.reason.${r as "slow"}`)).join(", ")}</>}
              </p>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
