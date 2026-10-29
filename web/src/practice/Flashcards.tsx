import { useQuery } from "@tanstack/react-query";
import { Check, Layers, RotateCcw, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type SetFilter } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { SpeakButton } from "../speech/SpeakButton";
import { useI18n } from "../i18n/I18nProvider";
import { Button, EmptyState, ErrorText, Skeleton } from "../components/ui";
import { CARDS } from "./constants";
import { useAnswerRecorder } from "./useRecorder";

/** Each answer is remembered (see useAnswerRecorder) so words come back when they are due. `due` asks for the words that are due
 * now. `round` makes a fresh draw each time the learner starts again; the cache is dropped as soon as the page is left. */
export function Flashcards({ language, set, due = false, onDone }: { language: string; set: SetFilter; due?: boolean; onDone: () => void }) {
  const { user } = useAuth();
  const { t, err } = useI18n();
  const [round, setRound] = useState(0);
  const cards = useQuery({ queryKey: ["practice", user!.id, "flashcards", language, String(set), due, round], queryFn: () => api.flashcards({ language, limit: CARDS, set, due }), gcTime: 0, staleTime: Infinity });
  const [index, setIndex] = useState(0);
  const [shown, setShown] = useState(false);
  const [known, setKnown] = useState(0);
  const { record, failed } = useAnswerRecorder(language);
  const again = () => { setRound((r) => r + 1); setIndex(0); setShown(false); setKnown(0); };

  if (cards.isPending) return <Skeleton className="h-40 w-full" />;
  if (cards.isError) return <ErrorText>{err(cards.error)}</ErrorText>;
  const items = cards.data.items;
  if (items.length === 0)
    return (
      <EmptyState icon={<Layers aria-hidden className="size-5" />} title={due ? t("practice.due.noneTitle") : t("practice.flashcards.noneTitle")}
        action={due ? <Button variant="secondary" onClick={onDone}>{t("common.back")}</Button>
          : <Link to="/vocabulary" className="text-sm font-medium text-brand-600 underline dark:text-brand-200">{t("practice.flashcards.addMeanings")}</Link>}>
        {due ? t("practice.due.noneBody") : t("practice.flashcards.noneBody")}
      </EmptyState>
    );
  if (index >= items.length)
    return (
      <div className="space-y-3 text-center" role="status">
        <p className="text-lg font-semibold text-slate-900">{t("practice.flashcards.score", { known, total: items.length })}</p>
        {failed && <ErrorText>{t("practice.saveFailed")}</ErrorText>}
        <div className="flex justify-center gap-2">
          <Button onClick={again} icon={<RotateCcw aria-hidden className="size-4" />}>{t("practice.again")}</Button>
          <Button variant="secondary" onClick={onDone}>{t("common.back")}</Button>
        </div>
      </div>
    );
  const card = items[index];
  const next = (knew: boolean) => { record(card.id, knew); if (knew) setKnown(known + 1); setShown(false); setIndex(index + 1); };
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">{t("practice.cardOf", { n: index + 1, total: items.length })}</p>
      <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-8 text-center dark:bg-slate-100/40">
        <p lang={language} className="text-2xl font-semibold text-slate-900">{card.word}</p>
        <SpeakButton text={card.word} language={language} />
        {shown && <p className="mt-3 text-base text-slate-700">{card.meaning}</p>}
      </div>
      {!shown ? (
        <Button onClick={() => setShown(true)}>{t("practice.showMeaning")}</Button>
      ) : (
        <div className="flex gap-2">
          <Button onClick={() => next(true)} icon={<Check aria-hidden className="size-4" />}>{t("practice.knewIt")}</Button>
          <Button variant="secondary" onClick={() => next(false)} icon={<X aria-hidden className="size-4" />}>{t("practice.notYet")}</Button>
        </div>
      )}
    </div>
  );
}
