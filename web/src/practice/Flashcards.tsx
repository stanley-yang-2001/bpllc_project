import { useQuery } from "@tanstack/react-query";
import { Layers, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type SetFilter } from "../api/client";
import type { Flashcard, FlashcardScope, Grade } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { SpeakButton } from "../speech/SpeakButton";
import { useI18n } from "../i18n/I18nProvider";
import { Badge, Button, EmptyState, ErrorText, Skeleton } from "../components/ui";
import { PictureThumb } from "../pictures/PictureThumb";
import { FlashcardSummary } from "./FlashcardSummary";
import { delayParts, remaining } from "./session";
import { useFlashcardRound } from "./useFlashcardRound";

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
  const { t } = useI18n();
  const { session, card, revealed, saving, failed, deadline, now, over, finished, reveal, grade } = useFlashcardRound({ language, cards, seconds });
  if (card === null || finished) return <FlashcardSummary language={language} set={set} session={session} failed={failed} timeUp={over} onMore={onMore} onDone={onDone} onPractise={onPractise} />;

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
          <div className="mt-4 flex flex-col items-center gap-3 border-t border-slate-200 pt-4">
            {card.picture && <PictureThumb picture={card.picture} size="lg" />}
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
