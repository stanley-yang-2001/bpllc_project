import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Layers, RotateCcw, TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, type SetFilter } from "../api/client";
import type { Flashcard, FlashcardScope, Grade } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useCelebrate } from "../rewards/Celebration";
import { milestoneFor } from "../rewards/effects";
import { rewardsKey } from "../api/keys";
import { SpeakButton } from "../speech/SpeakButton";
import { useI18n } from "../i18n/I18nProvider";
import { Badge, Button, EmptyState, ErrorText, Skeleton } from "../components/ui";
import { answered, delayParts, formatMs, remaining, startSession, summarize, take, type Session } from "./session";

/** Spaced-repetition flashcards. `scope` "due" is what the schedule asks for now (words in learning first, then reviews that are due,
 * then new words), "all" is every word of the chosen sets (practising ahead), "ids" is exactly those words. There is no card limit.
 * Each answer is one of four grades and is saved at once with how long it took; the server says when the word is due again. */
export function Flashcards({ language, set, scope, ids, seconds, onDone, onPractise }: {
  language: string; set: SetFilter; scope: FlashcardScope; ids?: number[]; seconds: number | null; onDone: () => void; onPractise: (ids: number[]) => void;
}) {
  const { user } = useAuth();
  const { t, err } = useI18n();
  const [round, setRound] = useState(0);
  const cards = useQuery({
    queryKey: ["practice", user!.id, "flashcards", language, String(set), scope, (ids ?? []).join(","), round],
    queryFn: () => api.flashcards({ language, set, scope, ids }), gcTime: 0, staleTime: Infinity,
  });
  if (cards.isPending) return <Skeleton className="h-40 w-full" />;
  if (cards.isError) return <ErrorText>{err(cards.error)}</ErrorText>;
  const items = cards.data.items;
  if (items.length === 0)
    return scope === "due" ? (
      <EmptyState icon={<Layers aria-hidden className="size-5" />} title={t("practice.due.noneTitle")} action={<Button variant="secondary" onClick={onDone}>{t("common.back")}</Button>}>
        {t("practice.due.noneBody")}
      </EmptyState>
    ) : (
      <EmptyState icon={<Layers aria-hidden className="size-5" />} title={t("practice.flashcards.noneTitle")}
        action={<Link to="/vocabulary" className="text-sm font-medium text-brand-600 underline dark:text-brand-200">{t("practice.flashcards.addMeanings")}</Link>}>
        {t("practice.flashcards.noneBody")}
      </EmptyState>
    );
  return <Round key={`${round}`} language={language} set={set} scope={scope} seconds={seconds} cards={items} onDone={onDone} onMore={() => setRound((r) => r + 1)} onPractise={onPractise} />;
}

function Round({ language, set, scope, seconds, cards, onDone, onMore, onPractise }: {
  language: string; set: SetFilter; scope: FlashcardScope; seconds: number | null; cards: Flashcard[]; onDone: () => void; onMore: () => void; onPractise: (ids: number[]) => void;
}) {
  const { user } = useAuth();
  const { t } = useI18n();
  const qc = useQueryClient();
  const celebrate = useCelebrate();
  const [start] = useState(() => take(startSession(cards), Date.now()));
  const [session, setSession] = useState<Session>(start.session);
  const [card, setCard] = useState<Flashcard | null>(start.card);
  const [deadline] = useState(() => (seconds ? Date.now() + seconds * 1000 : null));
  const [now, setNow] = useState(() => Date.now());
  const [timeUp, setTimeUp] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [failed, setFailed] = useState(false);
  const shownAt = useRef(performance.now());              // the card appeared
  const revealedAt = useRef<number | null>(null);          // the learner checked the answer

  const reveal = useCallback(() => {
    if (revealed || !card) return;
    revealedAt.current = performance.now();
    setRevealed(true);
  }, [revealed, card]);

  const grade = useCallback((g: Grade) => {
    if (!card || !revealed || saving || revealedAt.current === null) return;
    const now = performance.now();
    const think = Math.round(revealedAt.current - shownAt.current);
    const rate = Math.round(now - revealedAt.current);
    setSaving(true);
    const finish = (result: Awaited<ReturnType<typeof api.recordReviews>>[number] | null) => {
      const moved = answered(session, card, g, result, Date.now(), think, rate);
      const next = take(moved, Date.now());
      const hit = milestoneFor(moved.log);                    // a run of answers or a card count worth a celebration
      if (hit) celebrate(hit.level, t(hit.kind === "combo" ? "rewards.fx.combo" : "rewards.fx.cards", { n: hit.n }));
      setSession(next.session);
      setCard(deadline !== null && Date.now() >= deadline ? null : next.card);
      setRevealed(false);
      revealedAt.current = null;
      shownAt.current = performance.now();
      setSaving(false);
      void qc.invalidateQueries({ queryKey: ["practice", user!.id, "progress"] });
      void qc.invalidateQueries({ queryKey: ["practice", user!.id, "stats"] });
      void qc.invalidateQueries({ queryKey: ["practice", user!.id, "hardest"] });
      void qc.invalidateQueries({ queryKey: rewardsKey(user!.id, language) });
    };
    api.recordReviews([{ word_id: card.id, grade: g, think_ms: think, rate_ms: rate, mode: "flashcards", direction: "word" }])
      .then((r) => finish(r[0]))
      .catch(() => { setFailed(true); finish(null); });
  }, [card, revealed, saving, session, qc, user, celebrate, t, language, deadline]);

  useEffect(() => {                                           // keys 1 to 4 grade the answer, same as the buttons
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const el = e.target as HTMLElement | null;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable)) return;
      if (revealed && ["1", "2", "3", "4"].includes(e.key)) grade(Number(e.key) as Grade);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [revealed, grade]);

  useEffect(() => {
    if (deadline === null) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [deadline]);
  // when the time is up the card on screen is finished (so the answer being given is not lost), then the summary comes
  const over = deadline !== null && now >= deadline;
  useEffect(() => { if (over && !revealed && !saving) setTimeUp(true); }, [over, revealed, saving]);

  if (card === null || timeUp || (over && !revealed)) return <Done language={language} set={set} session={session} failed={failed} timeUp={over} onMore={onMore} onDone={onDone} onPractise={onPractise} />;

  const delay = (seconds: number) => { const { n, unit } = delayParts(seconds); return t(`practice.cards.in.${unit}`, { n }); };
  const grades: [Grade, string, number][] = [
    [1, t("practice.cards.again"), card.preview.again], [2, t("practice.cards.hard"), card.preview.hard],
    [3, t("practice.cards.good"), card.preview.good], [4, t("practice.cards.easy"), card.preview.easy],
  ];
  const ahead = scope !== "due" && card.status !== "new" && card.status !== "learning" && card.status !== "relearning";
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-slate-600" role="status">{t("practice.cards.left", { n: remaining(session) + 1 })}</p>
        {deadline !== null && <p className="text-sm tabular-nums text-slate-600" aria-label={t("practice.cards.timeLeft")}>{clock(deadline - now)}</p>}
      </div>
      <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-8 text-center dark:bg-slate-100/40">
        <div className="mb-3 flex justify-center gap-2">
          <Badge tone={card.status === "new" ? "brand" : "neutral"}>{t(`practice.cards.status.${card.status as "new"}`)}</Badge>
        </div>
        <p lang={language} className="text-2xl font-semibold text-slate-900">{card.word}</p>
        <SpeakButton text={card.word} language={language} />
        {revealed && (
          <div className="mt-4 border-t border-slate-200 pt-4">
            <p className="text-xl text-slate-800">{card.meaning}</p>
          </div>
        )}
      </div>
      {card.leech && revealed && (
        <p role="note" className="flex items-start gap-2 text-sm text-amber-800 dark:text-amber-300"><TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />{t("practice.cards.leech")}</p>
      )}
      {failed && <ErrorText>{t("practice.cards.saveFailed")}</ErrorText>}
      {!revealed ? (
        <Button onClick={reveal}>{t("practice.cards.reveal")}</Button>
      ) : (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" role="group" aria-label={t("practice.cards.gradeHelp")}>
          {grades.map(([g, label, secs]) => (
            <Button key={g} variant={g === 3 ? "primary" : "secondary"} disabled={saving} onClick={() => grade(g)} className="relative flex-col gap-0.5 py-2">
              <kbd aria-hidden className="absolute left-2 top-1 text-xs font-normal opacity-60">{g}</kbd>
              <span>{label}</span><span className="text-xs font-normal opacity-80">{delay(secs)}</span>
            </Button>
          ))}
        </div>
      )}
      {ahead && <p className="text-xs text-slate-600">{t("practice.cards.early")}</p>}
    </div>
  );
}

/** Time left as m:ss (never below 0:00). */
const clock = (ms: number) => { const total = Math.max(0, Math.ceil(ms / 1000)); return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`; };

function Done({ language, set, session, failed, timeUp, onMore, onDone, onPractise }: {
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
