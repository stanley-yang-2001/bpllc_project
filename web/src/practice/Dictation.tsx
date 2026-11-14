import { useQuery } from "@tanstack/react-query";
import { Headphones } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, type SetFilter } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { SpeakButton } from "../speech/SpeakButton";
import { useI18n } from "../i18n/I18nProvider";
import { Button, EmptyState, ErrorText, inputCls, Skeleton } from "../components/ui";
import { CARDS } from "./constants";
import { checkTyped, type TypedResult } from "./typed";
import { PromptPanel, QuizFeedback, QuizScore, useQuizRound } from "./quiz";

/** Hear a word read aloud by the browser, type it, and be told. Each answer is remembered like any other practice. */
export function Dictation({ language, set, due = false, onDone }: { language: string; set: SetFilter; due?: boolean; onDone: () => void }) {
  const { user } = useAuth();
  const { t, err } = useI18n();
  const [round, setRound] = useState(0);
  const words = useQuery({ queryKey: ["practice", user!.id, "dictation", language, String(set), due, round], queryFn: () => api.dictation({ language, limit: CARDS, set, due }), gcTime: 0, staleTime: Infinity });
  const { index, right, failed, grade, next, restart } = useQuizRound(language, words.isSuccess);
  const [typed, setTyped] = useState("");
  const [result, setResult] = useState<TypedResult | null>(null);
  useEffect(() => { setTyped(""); setResult(null); }, [index]);
  const again = () => { setRound((r) => r + 1); restart(); };

  if (words.isPending) return <Skeleton className="h-40 w-full" />;
  if (words.isError) return <ErrorText>{err(words.error)}</ErrorText>;
  const items = words.data.items;
  if (items.length === 0)
    return (
      <EmptyState icon={<Headphones aria-hidden className="size-5" />} title={due ? t("practice.due.noneTitle") : t("practice.dictation.noneTitle")}
        action={due ? <Button variant="secondary" onClick={onDone}>{t("common.back")}</Button>
          : <Link to="/vocabulary" className="text-sm font-medium text-brand-600 underline dark:text-brand-200">{t("practice.dictation.addWords")}</Link>}>
        {due ? t("practice.due.noneBody") : t("practice.dictation.noneBody")}
      </EmptyState>
    );
  if (index >= items.length)
    return <QuizScore title={t("practice.choice.score", { right, total: items.length })} againLabel={t("practice.again")} failed={failed} onAgain={again} onDone={onDone} />;
  const item = items[index];
  const check = (e: FormEvent) => {
    e.preventDefault();
    if (result !== null || typed.trim() === "") return;
    const r = checkTyped(typed, item.word);
    setResult(r);
    grade(item.id, r === "right", { mode: "dictation" });
  };
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">{t("practice.cardOf", { n: index + 1, total: items.length })}</p>
      <PromptPanel>
        <p className="mb-2 text-sm text-slate-600">{t("practice.dictation.prompt")}</p>
        <SpeakButton text={item.word} language={language} label={t("speech.listen")} slow />
      </PromptPanel>
      <form onSubmit={check} className="space-y-3">
        <div>
          <label htmlFor="dictation-answer" className="mb-1 block text-sm font-medium text-slate-700">{t("practice.dictation.input")}</label>
          <input id="dictation-answer" lang={language} className={inputCls} value={typed} onChange={(e) => setTyped(e.target.value)} readOnly={result !== null}
            autoComplete="off" autoCapitalize="off" autoCorrect="off" spellCheck={false} autoFocus />
        </div>
        {result === null && <Button type="submit" disabled={typed.trim() === ""}>{t("practice.dictation.check")}</Button>}
      </form>
      {result !== null && (
        <QuizFeedback correct={result === "right"} last={index + 1 === items.length} onNext={next}
          message={result === "right" ? t("practice.cloze.correct") : result === "accents" ? t("practice.dictation.accents", { answer: item.word }) : t("practice.dictation.wrong", { answer: item.word })}>
          {item.meaning && <p className="text-sm text-slate-600">{item.meaning}</p>}
        </QuizFeedback>
      )}
    </div>
  );
}
