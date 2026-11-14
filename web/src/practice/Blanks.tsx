import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { api, type ClozeItem } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n/I18nProvider";
import { Button, ErrorText, Skeleton } from "../components/ui";
import { QuizFeedback, QuizScore, useQuizRound } from "./quiz";

/** Fill in the blank in a saved story, one word at a time. Each answer is remembered against the learner's word. */
export function Blanks({ storyId, onDone }: { storyId: number; onDone: () => void }) {
  const { user } = useAuth();
  const { t, err } = useI18n();
  const set = useQuery({ queryKey: ["practice", user!.id, "cloze", storyId], queryFn: () => api.cloze(storyId), gcTime: 0, staleTime: Infinity });
  const { index, picked, right, failed, choose: pick, next, restart } = useQuizRound(set.data?.language ?? "", set.isSuccess);
  useEffect(() => { restart(); }, [storyId]);   // eslint-disable-line react-hooks/exhaustive-deps

  if (set.isPending) return <Skeleton className="h-40 w-full" />;
  if (set.isError) return <ErrorText>{err(set.error)}</ErrorText>;
  const items: ClozeItem[] = set.data.items;
  if (index >= items.length)
    return <QuizScore title={t("practice.cloze.score", { right, total: items.length })} againLabel={t("common.tryAgain")} failed={failed} onAgain={restart} onDone={onDone} />;
  const item = items[index];
  const choose = (choice: string) => pick(choice, item.word_id, choice === item.answer, { mode: "cloze" });
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">{t("practice.cloze.sentenceOf", { n: index + 1, total: items.length })}</p>
      <p lang={set.data.language} className="text-lg leading-relaxed text-slate-900">
        {item.before}<span className="mx-1 inline-block min-w-16 border-b-2 border-slate-400 text-center font-semibold">{picked !== null ? item.answer : " "}</span>{item.after}
      </p>
      {item.hint && <p className="text-sm text-slate-600">{t("practice.cloze.hint", { hint: item.hint })}</p>}
      <div className="flex flex-wrap gap-2" role="group" aria-label={t("practice.cloze.choices")}>
        {item.choices.map((c) => (
          <Button key={c} variant="secondary" onClick={() => choose(c)} disabled={picked !== null && c !== picked && c !== item.answer} lang={set.data.language}>{c}</Button>
        ))}
      </div>
      {picked !== null && (
        <QuizFeedback correct={picked === item.answer} last={index + 1 === items.length} onNext={next}
          message={picked === item.answer ? t("practice.cloze.correct") : t("practice.cloze.wrong", { answer: item.answer })} />
      )}
    </div>
  );
}
