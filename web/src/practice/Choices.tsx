import { useQuery } from "@tanstack/react-query";
import { ListChecks, RotateCcw } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type SetFilter } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { SpeakButton } from "../speech/SpeakButton";
import { useI18n } from "../i18n/I18nProvider";
import { Button, EmptyState, ErrorText, Skeleton } from "../components/ui";
import { CARDS } from "./constants";
import { useAnswerRecorder } from "./useRecorder";

export type Direction = "meaning" | "word";

/** Four options per question, made from the learner's own words that have a meaning. Each answer is remembered (useAnswerRecorder);
 * `due` asks about the words that are due now. */
export function Choices({ language, set, direction, due = false, onDone }: { language: string; set: SetFilter; direction: Direction; due?: boolean; onDone: () => void }) {
  const { user } = useAuth();
  const { t, err } = useI18n();
  const [round, setRound] = useState(0);
  const cards = useQuery({ queryKey: ["practice", user!.id, "choices", language, String(set), direction, due, round], queryFn: () => api.choices({ language, limit: CARDS, direction, set, due }), gcTime: 0, staleTime: Infinity });
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [right, setRight] = useState(0);
  const { record, failed } = useAnswerRecorder(language);
  const again = () => { setRound((r) => r + 1); setIndex(0); setPicked(null); setRight(0); };

  if (cards.isPending) return <Skeleton className="h-40 w-full" />;
  if (cards.isError) return <ErrorText>{err(cards.error)}</ErrorText>;
  const items = cards.data.items;
  if (items.length === 0)
    return (
      <EmptyState icon={<ListChecks aria-hidden className="size-5" />} title={due && cards.data.total >= 2 ? t("practice.due.noneTitle") : t("practice.choice.noneTitle")}
        action={due && cards.data.total >= 2 ? <Button variant="secondary" onClick={onDone}>{t("common.back")}</Button>
          : <Link to="/vocabulary" className="text-sm font-medium text-brand-600 underline dark:text-brand-200">{t("practice.flashcards.addMeanings")}</Link>}>
        {due && cards.data.total >= 2 ? t("practice.due.noneBody") : t("practice.choice.noneBody")}
      </EmptyState>
    );
  if (index >= items.length)
    return (
      <div className="space-y-3 text-center" role="status">
        <p className="text-lg font-semibold text-slate-900">{t("practice.choice.score", { right, total: items.length })}</p>
        {failed && <ErrorText>{t("practice.saveFailed")}</ErrorText>}
        <div className="flex justify-center gap-2">
          <Button onClick={again} icon={<RotateCcw aria-hidden className="size-4" />}>{t("practice.again")}</Button>
          <Button variant="secondary" onClick={onDone}>{t("common.back")}</Button>
        </div>
      </div>
    );
  const item = items[index];
  const choose = (c: string) => {
    if (picked !== null) return;
    setPicked(c);
    record(item.id, c === item.answer);
    if (c === item.answer) setRight(right + 1);
  };
  const wordSide = direction === "meaning";        // the question is a word; the options are meanings
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">{t("practice.cardOf", { n: index + 1, total: items.length })}</p>
      <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-8 text-center dark:bg-slate-100/40">
        <p lang={wordSide ? language : undefined} className="text-2xl font-semibold text-slate-900">{item.prompt}</p>
        {wordSide && <SpeakButton text={item.prompt} language={language} />}
      </div>
      <div className="grid gap-2" role="group" aria-label={t("practice.choice.options")}>
        {item.choices.map((c) => (
          <Button key={c} variant="secondary" className="justify-start text-left" lang={wordSide ? undefined : language} onClick={() => choose(c)}
            disabled={picked !== null && c !== picked && c !== item.answer}>{c}</Button>
        ))}
      </div>
      {picked !== null && (
        <div className="space-y-2" role="status">
          <p className={picked === item.answer ? "font-medium text-emerald-700 dark:text-emerald-400" : "font-medium text-red-700 dark:text-red-400"}>
            {picked === item.answer ? t("practice.choice.correct") : t("practice.choice.wrong", { answer: item.answer })}
          </p>
          <Button onClick={() => { setPicked(null); setIndex(index + 1); }}>{index + 1 === items.length ? t("practice.cloze.seeResult") : t("common.next")}</Button>
        </div>
      )}
    </div>
  );
}
