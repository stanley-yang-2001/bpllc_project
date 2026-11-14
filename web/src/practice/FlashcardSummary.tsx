import { useQuery } from "@tanstack/react-query";
import { RotateCcw } from "lucide-react";
import { api, type SetFilter } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n/I18nProvider";
import { Button, ErrorText } from "../components/ui";
import { formatMs, summarize, type Session } from "./session";

/** The screen after a flashcard session (all answered, or time ran out): this session's numbers, the words that were slow or missed,
 * and the all-time totals. */
export function FlashcardSummary({ language, set, session, failed, timeUp, onMore, onDone, onPractise }: {
  language: string; set: SetFilter; session: Session; failed: boolean; timeUp: boolean; onMore: () => void; onDone: () => void; onPractise: (ids: number[]) => void;
}) {
  const { t } = useI18n();
  const { user } = useAuth();
  const s = summarize(session.log);
  const c = s.counts;
  const total = useQuery({ queryKey: ["practice", user!.id, "stats", language, String(set)], queryFn: () => api.studyStats(language, set) }).data;
  return (
    <div className="space-y-4" role="status">
      <div className="text-center">
        <p className="text-lg font-semibold text-slate-900">{t(timeUp ? "practice.cards.timeUpTitle" : "practice.cards.doneTitle")}</p>
        <p className="text-sm text-slate-700">{t("practice.cards.summary", { answers: s.answers, words: s.words })}</p>
      </div>
      <dl className="grid grid-cols-2 gap-3 text-center">
        <div><dd className="text-2xl font-semibold text-slate-900">{Math.round(s.accuracy * 100)}%</dd><dt className="text-xs text-slate-600">{t("practice.stats.accuracy")}</dt></div>
        <div><dd className="text-2xl font-semibold text-slate-900">{formatMs(s.avgThinkMs)}</dd><dt className="text-xs text-slate-600">{t("practice.stats.avgTime")}</dt></div>
      </dl>
      <p className="text-center text-sm text-slate-700">{t("practice.cards.grades", { a: c[1], h: c[2], g: c[3], e: c[4] })}</p>
      {s.slowest.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-slate-700">{t("practice.cards.slowest")}</h3>
          <ul className="mt-1 text-sm text-slate-800">{s.slowest.map((w) => <li key={w.id}><span lang={language} className="font-medium">{w.word}</span> · {formatMs(w.ms)}</li>)}</ul>
        </div>
      )}
      {s.missed.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-slate-700">{t("practice.cards.missed")}</h3>
          <p lang={language} className="text-sm text-slate-800">{s.missed.map((w) => w.word).join(", ")}</p>
        </div>
      )}
      {total && total.total_reviews > 0 && (
        <div className="rounded-lg border border-slate-200 p-3">
          <h3 className="text-sm font-medium text-slate-700">{t("practice.cards.allTime")}</h3>
          <p className="mt-1 text-sm text-slate-800">{t("practice.cards.allTimeLine", { answers: total.total_reviews, words: total.total_words_practised, days: total.total_days })}</p>
          <p className="text-sm text-slate-800">
            {t("practice.cards.allTimeRates", { pct: Math.round((total.total_accuracy ?? 0) * 100), time: total.total_avg_think_ms == null ? "–" : formatMs(total.total_avg_think_ms), studied: t("practice.stats.minutes", { n: Math.max(1, Math.round(total.total_studied_seconds / 60)) }) })}
            {total.total_retention != null && <> · {t("practice.cards.allTimeRetention", { pct: Math.round(total.total_retention * 100) })}</>}
          </p>
        </div>
      )}
      {failed && <ErrorText>{t("practice.cards.saveFailed")}</ErrorText>}
      <div className="flex flex-wrap justify-center gap-2">
        <Button onClick={onMore} icon={<RotateCcw aria-hidden className="size-4" />}>{t("practice.cards.studyMore")}</Button>
        {s.missed.length > 0 && <Button variant="secondary" onClick={() => onPractise(s.missed.map((w) => w.id))}>{t("practice.cards.practiseMissed", { n: s.missed.length })}</Button>}
        <Button variant="secondary" onClick={onDone}>{t("common.back")}</Button>
      </div>
    </div>
  );
}
