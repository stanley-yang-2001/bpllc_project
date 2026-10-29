import { useQuery } from "@tanstack/react-query";
import { Headphones, RotateCcw } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, type SetFilter } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { SpeakButton } from "../speech/SpeakButton";
import { useI18n } from "../i18n/I18nProvider";
import { Button, EmptyState, ErrorText, inputCls, Skeleton } from "../components/ui";
import { CARDS } from "./constants";
import { checkTyped, type TypedResult } from "./typed";
import { useAnswerRecorder } from "./useRecorder";

/** Hear a word read aloud by the browser, type it, and be told. Each answer is remembered like any other practice. */
export function Dictation({ language, set, due = false, onDone }: { language: string; set: SetFilter; due?: boolean; onDone: () => void }) {
  const { user } = useAuth();
  const { t, err } = useI18n();
  const [round, setRound] = useState(0);
  const words = useQuery({ queryKey: ["practice", user!.id, "dictation", language, String(set), due, round], queryFn: () => api.dictation({ language, limit: CARDS, set, due }), gcTime: 0, staleTime: Infinity });
  const [index, setIndex] = useState(0);
  const [typed, setTyped] = useState("");
  const [result, setResult] = useState<TypedResult | null>(null);
  const [right, setRight] = useState(0);
  const { record, failed } = useAnswerRecorder(language);
  useEffect(() => { setTyped(""); setResult(null); }, [index]);
  const again = () => { setRound((r) => r + 1); setIndex(0); setRight(0); };

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
  const check = (e: FormEvent) => {
    e.preventDefault();
    if (result !== null || typed.trim() === "") return;
    const r = checkTyped(typed, item.word);
    setResult(r);
    record(item.id, r === "right");
    if (r === "right") setRight(right + 1);
  };
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">{t("practice.cardOf", { n: index + 1, total: items.length })}</p>
      <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-8 text-center dark:bg-slate-100/40">
        <p className="mb-2 text-sm text-slate-600">{t("practice.dictation.prompt")}</p>
        <SpeakButton text={item.word} language={language} label={t("speech.listen")} slow />
      </div>
      <form onSubmit={check} className="space-y-3">
        <div>
          <label htmlFor="dictation-answer" className="mb-1 block text-sm font-medium text-slate-700">{t("practice.dictation.input")}</label>
          <input id="dictation-answer" lang={language} className={inputCls} value={typed} onChange={(e) => setTyped(e.target.value)} readOnly={result !== null}
            autoComplete="off" autoCapitalize="off" autoCorrect="off" spellCheck={false} autoFocus />
        </div>
        {result === null && <Button type="submit" disabled={typed.trim() === ""}>{t("practice.dictation.check")}</Button>}
      </form>
      {result !== null && (
        <div className="space-y-2" role="status">
          <p className={result === "right" ? "font-medium text-emerald-700 dark:text-emerald-400" : "font-medium text-red-700 dark:text-red-400"}>
            {result === "right" ? t("practice.cloze.correct") : result === "accents" ? t("practice.dictation.accents", { answer: item.word }) : t("practice.dictation.wrong", { answer: item.word })}
          </p>
          {item.meaning && <p className="text-sm text-slate-600">{item.meaning}</p>}
          <Button onClick={() => setIndex(index + 1)}>{index + 1 === items.length ? t("practice.cloze.seeResult") : t("common.next")}</Button>
        </div>
      )}
    </div>
  );
}
