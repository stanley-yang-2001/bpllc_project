import { Layers } from "lucide-react";
import { useState } from "react";
import { useI18n } from "../../i18n/I18nProvider";
import { Button } from "../../components/ui";
import { Flashcards } from "../Flashcards";
import { LengthPicker, MIN_SECONDS } from "../LengthPicker";
import { ModeTile } from "./ModeTile";
import type { PracticeMode } from "./types";

const LENGTH_KEY = "tutor.cards.seconds";
const DEFAULT_SECONDS = 600;
/** The session length the learner chose last time in seconds (0 = no limit), or 10 minutes. */
function storedSeconds(): number | null {
  try {
    const v = localStorage.getItem(LENGTH_KEY);
    if (v === null) return DEFAULT_SECONDS;
    const n = Number(v);
    return n === 0 ? null : Number.isFinite(n) && n >= MIN_SECONDS ? n : DEFAULT_SECONDS;
  } catch { return DEFAULT_SECONDS; }
}
/** How long a flashcard session lasts (null = until the words run out), kept on this device. The menu card sets it and the session
 * reads it, so every way into flashcards (the menu, "review due", "practise the missed words") uses the same length. */
function useCardSeconds() {
  const [seconds, setSeconds] = useState<number | null>(storedSeconds);
  const choose = (v: number | null) => { setSeconds(v); try { localStorage.setItem(LENGTH_KEY, String(v ?? 0)); } catch { /* not kept */ } };
  return [seconds, choose] as const;
}

export const CardsMode: PracticeMode<"cards"> = {
  Tile({ ctx, start }) {
    const { t } = useI18n();
    const [seconds, chooseSeconds] = useCardSeconds();
    const p = ctx.progress;
    const wordCount = p ? p.new + p.learning + p.known : 0;
    return (
      <ModeTile icon={Layers} title={t("practice.flashcards.title")} text={t("practice.cards.text", { language: ctx.name })}>
        {p && <p className="text-xs text-slate-600">{t("practice.cards.counts", { due: p.due, new: p.new, n: wordCount })}</p>}
        <LengthPicker value={seconds} onChange={chooseSeconds} />
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => start({ mode: "cards", scope: "due", ids: [] })}>{t("practice.cards.studyDue")}</Button>
          <Button variant="secondary" onClick={() => start({ mode: "cards", scope: "all", ids: [] })}>{t("practice.cards.studyAll", { n: wordCount })}</Button>
        </div>
      </ModeTile>
    );
  },
  Session({ ctx, launch, onDone, start }) {
    const [seconds] = useCardSeconds();
    return <Flashcards language={ctx.language} set={ctx.set} scope={launch.scope} ids={launch.ids} seconds={seconds} onDone={onDone} onPractise={(ids) => start({ mode: "cards", scope: "ids", ids })} />;
  },
};
