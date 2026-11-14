import { useQuery } from "@tanstack/react-query";
import { Tags } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type SetFilter } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { SpeakButton } from "../speech/SpeakButton";
import { useI18n } from "../i18n/I18nProvider";
import { Button, EmptyState, ErrorText, Skeleton } from "../components/ui";
import { posKeyOf } from "../vocab/usePos";
import { CARDS } from "./constants";
import { PromptPanel, QuizFeedback, QuizScore, useQuizRound } from "./quiz";

/** Is this word a noun, a verb, an adjective ...? The options are the categories of the language being studied (each language has
 * its own list). Uses the learner's own labelled words; each answer is remembered like any other practice. */
export function PosPractice({ language, set, due = false, onDone }: { language: string; set: SetFilter; due?: boolean; onDone: () => void }) {
  const { user } = useAuth();
  const { t, err } = useI18n();
  const [round, setRound] = useState(0);
  const cards = useQuery({ queryKey: ["practice", user!.id, "pos", language, String(set), due, round], queryFn: () => api.posCards({ language, limit: CARDS, set, due }), gcTime: 0, staleTime: Infinity });
  const { index, picked, right, failed, choose: pick, next, restart } = useQuizRound(language, cards.isSuccess);
  const again = () => { setRound((r) => r + 1); restart(); };
  const name = (code: string) => { const k = posKeyOf(code); return k ? t(k) : code; };

  if (cards.isPending) return <Skeleton className="h-40 w-full" />;
  if (cards.isError) return <ErrorText>{err(cards.error)}</ErrorText>;
  const items = cards.data.items;
  if (items.length === 0)
    return (
      <EmptyState icon={<Tags aria-hidden className="size-5" />} title={due && cards.data.total > 0 ? t("practice.due.noneTitle") : t("practice.pos.noneTitle")}
        action={due && cards.data.total > 0 ? <Button variant="secondary" onClick={onDone}>{t("common.back")}</Button>
          : <Link to="/vocabulary" className="text-sm font-medium text-brand-600 underline dark:text-brand-200">{t("practice.pos.label")}</Link>}>
        {due && cards.data.total > 0 ? t("practice.due.noneBody") : t("practice.pos.noneBody")}
      </EmptyState>
    );
  if (index >= items.length)
    return <QuizScore title={t("practice.choice.score", { right, total: items.length })} againLabel={t("practice.again")} failed={failed} onAgain={again} onDone={onDone} />;
  const item = items[index];
  const choose = (code: string) => pick(code, item.id, code === item.answer, { mode: "pos" });
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">{t("practice.cardOf", { n: index + 1, total: items.length })}</p>
      <PromptPanel>
        <p className="mb-2 text-sm text-slate-600">{t("practice.pos.prompt")}</p>
        <p lang={language} className="text-2xl font-semibold text-slate-900">{item.word}</p>
        <SpeakButton text={item.word} language={language} />
        {item.meaning && <p className="mt-2 text-sm text-slate-600">{item.meaning}</p>}
      </PromptPanel>
      <div className="grid gap-2 sm:grid-cols-2" role="group" aria-label={t("practice.choice.options")}>
        {item.options.map((c) => (
          <Button key={c} variant="secondary" className="justify-start text-left" onClick={() => choose(c)} disabled={picked !== null && c !== picked && c !== item.answer}>{name(c)}</Button>
        ))}
      </div>
      {picked !== null && (
        <QuizFeedback correct={picked === item.answer} last={index + 1 === items.length} onNext={next}
          message={picked === item.answer ? t("practice.cloze.correct") : t("practice.pos.wrong", { answer: name(item.answer) })} />
      )}
    </div>
  );
}
