import { useQuery } from "@tanstack/react-query";
import { ListChecks } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type SetFilter } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { SpeakButton } from "../speech/SpeakButton";
import { useI18n } from "../i18n/I18nProvider";
import { Button, EmptyState, ErrorText, Skeleton } from "../components/ui";
import { PictureThumb } from "../pictures/PictureThumb";
import { CARDS } from "./constants";
import { PromptPanel, QuizFeedback, QuizScore, useQuizRound } from "./quiz";

/** What the learner is shown: the word (options are meanings), the meaning (options are words), or the word's picture (options are words). */
export type Direction = "meaning" | "word" | "picture";

/** Four options per question, made from the learner's own words that have a meaning. Each answer is remembered (useAnswerRecorder);
 * `due` asks about the words that are due now. */
export function Choices({ language, set, direction, due = false, onDone }: { language: string; set: SetFilter; direction: Direction; due?: boolean; onDone: () => void }) {
  const { user } = useAuth();
  const { t, err } = useI18n();
  const [round, setRound] = useState(0);
  const cards = useQuery({ queryKey: ["practice", user!.id, "choices", language, String(set), direction, due, round], queryFn: () => api.choices({ language, limit: CARDS, direction, set, due }), gcTime: 0, staleTime: Infinity });
  const { index, picked, right, failed, choose: pick, next, restart } = useQuizRound(language, cards.isSuccess);
  const again = () => { setRound((r) => r + 1); restart(); };

  if (cards.isPending) return <Skeleton className="h-40 w-full" />;
  if (cards.isError) return <ErrorText>{err(cards.error)}</ErrorText>;
  const items = cards.data.items;
  if (items.length === 0 && direction === "picture")
    return (
      <EmptyState icon={<ListChecks aria-hidden className="size-5" />} title={t("pictures.quizNoneTitle")}
        action={<Link to="/vocabulary" className="text-sm font-medium text-brand-600 underline dark:text-brand-200">{t("practice.flashcards.addMeanings")}</Link>}>
        {t("pictures.quizNoneBody")}
      </EmptyState>
    );
  if (items.length === 0)
    return (
      <EmptyState icon={<ListChecks aria-hidden className="size-5" />} title={due && cards.data.total >= 2 ? t("practice.due.noneTitle") : t("practice.choice.noneTitle")}
        action={due && cards.data.total >= 2 ? <Button variant="secondary" onClick={onDone}>{t("common.back")}</Button>
          : <Link to="/vocabulary" className="text-sm font-medium text-brand-600 underline dark:text-brand-200">{t("practice.flashcards.addMeanings")}</Link>}>
        {due && cards.data.total >= 2 ? t("practice.due.noneBody") : t("practice.choice.noneBody")}
      </EmptyState>
    );
  if (index >= items.length)
    return <QuizScore title={t("practice.choice.score", { right, total: items.length })} againLabel={t("practice.again")} failed={failed} onAgain={again} onDone={onDone} />;
  const item = items[index];
  const wordIsPrompt = direction === "meaning";               // the prompt is the word (the options are meanings)
  const choose = (c: string) => pick(c, item.id, c === item.answer, { mode: "choices", direction: direction === "picture" ? "picture" : wordIsPrompt ? "word" : "meaning" });
  const wordSide = direction === "meaning";        // the question is a word; the options are meanings
  const pictured = direction === "picture" && item.picture;
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">{t("practice.cardOf", { n: index + 1, total: items.length })}</p>
      <PromptPanel>
        {pictured ? (
          <div className="flex justify-center">
            <PictureThumb picture={item.picture!} size="lg" />
            <span className="sr-only">{item.prompt}</span>      {/* the meaning, for someone who cannot see the picture */}
          </div>
        ) : (
          <>
            <p lang={wordSide ? language : undefined} className="text-2xl font-semibold text-slate-900">{item.prompt}</p>
            {wordSide && <SpeakButton text={item.prompt} language={language} />}
          </>
        )}
      </PromptPanel>
      <div className="grid gap-2" role="group" aria-label={t("practice.choice.options")}>
        {item.choices.map((c) => (
          <Button key={c} variant="secondary" className="justify-start text-left" lang={wordSide ? undefined : language} onClick={() => choose(c)}
            disabled={picked !== null && c !== picked && c !== item.answer}>{c}</Button>
        ))}
      </div>
      {picked !== null && (
        <QuizFeedback correct={picked === item.answer} last={index + 1 === items.length} onNext={next}
          message={picked === item.answer ? t("practice.choice.correct") : t("practice.choice.wrong", { answer: item.answer })} />
      )}
    </div>
  );
}
