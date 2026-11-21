import { useEffect, useMemo, useState } from "react";
import { useI18n } from "../i18n/I18nProvider";
import { segments } from "./segments";
import { useGloss } from "./useGloss";
import { WordCard } from "./WordCard";

const KNOWN = "m-0 inline cursor-pointer rounded-sm border-0 bg-transparent p-0 text-inherit underline decoration-brand-500 decoration-dotted decoration-2 underline-offset-4 " +
  "hover:bg-brand-50 focus-visible:outline-2 focus-visible:outline-brand-500 dark:hover:bg-brand-900/40";
const OTHER = "cursor-pointer rounded-sm hover:bg-slate-100 dark:hover:bg-slate-800";
const CHOSEN = "bg-brand-100 dark:bg-brand-900/60";

/** A story with the learner's own words underlined. Tap an underlined word for its meaning, tap any other word to hear it or add it to the list.
 * The text shows plain at once and the underlines come when the API has answered; if it never does, the story is still the story.
 * Underlined words are real buttons (the way in for the keyboard and a screen reader); the other words answer a tap or a click only, since a
 * button on every word would put hundreds of stops in a story. */
export function GlossedText({ text, language, className = "" }: { text: string; language: string; className?: string }) {
  const { t } = useI18n();
  const gloss = useGloss(text, language);
  const [chosen, setChosen] = useState<{ start: number; end: number } | null>(null);
  useEffect(() => setChosen(null), [text, language]);
  const parts = useMemo(() => (gloss.data ? segments(text, gloss.data.spans, language) : null), [gloss.data, text, language]);
  const frame = `whitespace-pre-wrap break-words text-base leading-relaxed text-slate-900 ${className}`;
  if (!parts || !gloss.data) return <p lang={language} className={frame}>{text}</p>;
  const pick = (p: { start: number; end: number }) => setChosen(chosen?.start === p.start ? null : { start: p.start, end: p.end });
  return (
    <div>
      <p lang={language} className={frame}>
        {parts.map((p) => {
          if (p.kind === "text") return <span key={p.start}>{p.text}</span>;
          const on = chosen?.start === p.start;
          if (p.kind === "known") {
            return <button key={p.start} type="button" aria-pressed={on} onClick={() => pick(p)} className={`${KNOWN} ${on ? CHOSEN : ""}`}>{p.text}</button>;
          }
          return <span key={p.start} onClick={() => pick(p)} className={`${OTHER} ${on ? CHOSEN : ""}`}>{p.text}</span>;
        })}
      </p>
      <p className="mt-1 text-xs text-slate-600">{t("reader.hint")}</p>
      {chosen && <WordCard text={text} language={language} at={chosen} gloss={gloss.data} onClose={() => setChosen(null)} />}
    </div>
  );
}
