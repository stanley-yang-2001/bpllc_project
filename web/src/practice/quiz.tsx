import { RotateCcw } from "lucide-react";
import { useState, type ReactNode } from "react";
import type { Answer } from "../api/types";
import { useI18n } from "../i18n/I18nProvider";
import { Button, ErrorText } from "../components/ui";
import { useAnswerRecorder, useThinkTimer } from "./useRecorder";

/** What the four question-and-answer modes (Choices, PosPractice, Dictation, Blanks) share: which question we are on, the score, the
 * chosen option, the think timer and saving each answer. A mode keeps only what is its own: where its questions come from and how one
 * question looks. `ready` = the questions have loaded (the think timer starts then). */
export function useQuizRound(language: string, ready: boolean) {
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [right, setRight] = useState(0);
  const { record, failed } = useAnswerRecorder(language);
  const elapsed = useThinkTimer(index, ready);
  type Extra = Pick<Answer, "mode" | "direction">;
  /** Save this answer (with how long the question was on screen) and count it when right. */
  const grade = (wordId: number | null | undefined, correct: boolean, extra: Extra) => {
    record(wordId, correct, { think_ms: elapsed(), ...extra });
    if (correct) setRight((n) => n + 1);
  };
  /** An option was picked: only the first pick of a question counts. */
  const choose = (choice: string, wordId: number | null | undefined, correct: boolean, extra: Extra) => {
    if (picked !== null) return;
    setPicked(choice);
    grade(wordId, correct, extra);
  };
  const next = () => { setPicked(null); setIndex((i) => i + 1); };
  const restart = () => { setIndex(0); setPicked(null); setRight(0); };
  return { index, picked, right, failed, grade, choose, next, restart };
}

/** The framed box a question is shown in. */
export function PromptPanel({ children }: { children: ReactNode }) {
  return <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-8 text-center dark:bg-slate-100/40">{children}</div>;
}

/** The end-of-round screen: the score, a notice if saving failed, and "again" / "back". */
export function QuizScore({ title, againLabel, failed, onAgain, onDone }: { title: string; againLabel: string; failed: boolean; onAgain: () => void; onDone: () => void }) {
  const { t } = useI18n();
  return (
    <div className="space-y-3 text-center" role="status">
      <p className="text-lg font-semibold text-slate-900">{title}</p>
      {failed && <ErrorText>{t("practice.saveFailed")}</ErrorText>}
      <div className="flex justify-center gap-2">
        <Button onClick={onAgain} icon={<RotateCcw aria-hidden className="size-4" />}>{againLabel}</Button>
        <Button variant="secondary" onClick={onDone}>{t("common.back")}</Button>
      </div>
    </div>
  );
}

/** Right or wrong after an answer, anything the mode adds (`children`), and the button to the next question (or the result). */
export function QuizFeedback({ correct, message, last, onNext, children }: { correct: boolean; message: string; last: boolean; onNext: () => void; children?: ReactNode }) {
  const { t } = useI18n();
  return (
    <div className="space-y-2" role="status">
      <p className={correct ? "font-medium text-emerald-700 dark:text-emerald-400" : "font-medium text-red-700 dark:text-red-400"}>{message}</p>
      {children}
      <Button onClick={onNext}>{last ? t("practice.cloze.seeResult") : t("common.next")}</Button>
    </div>
  );
}
