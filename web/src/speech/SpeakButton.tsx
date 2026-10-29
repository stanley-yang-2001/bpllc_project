import { Square, Volume2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useI18n } from "../i18n/I18nProvider";
import { Button } from "../components/ui";
import { NORMAL_RATE, SLOW_RATE, speak, speechSupported } from "./speak";

/** One read-aloud button (an icon for a word, a labelled pair for a story). Renders nothing when the browser has no speech engine.
 * Only one text is read at a time across the page: starting another stops the first (speak() cancels the queue). */
export function SpeakButton({ text, language, label, slow = false }: { text: string; language: string; label?: string; slow?: boolean }) {
  const { t } = useI18n();
  const [mode, setMode] = useState<"idle" | "normal" | "slow">("idle");
  const [problem, setProblem] = useState<"voice" | "error" | null>(null);
  const stop = useRef<() => void>(() => undefined);
  const alive = useRef(true);
  useEffect(() => () => { alive.current = false; stop.current(); }, []);
  useEffect(() => { stop.current(); setMode("idle"); }, [text, language]);
  if (!speechSupported()) return null;

  const run = (m: "normal" | "slow") => {
    if (mode === m) { stop.current(); setMode("idle"); return; }
    setProblem(null);
    setMode(m);
    stop.current = speak(text, language, m === "slow" ? SLOW_RATE : NORMAL_RATE, {
      onEnd: () => alive.current && setMode("idle"),
      onNoVoice: () => { if (alive.current) { setMode("idle"); setProblem("voice"); } },
      onError: () => { if (alive.current) { setMode("idle"); setProblem("error"); } },
    });
  };
  const shown = text.length > 24 ? `${text.slice(0, 24)}…` : text;
  const button = (m: "normal" | "slow", caption: string, aria: string) => (
    <Button type="button" variant="ghost" aria-pressed={mode === m} aria-label={aria} onClick={() => run(m)} icon={mode === m ? <Square aria-hidden className="size-4" /> : <Volume2 aria-hidden className="size-4" />}>
      {label !== undefined ? (mode === m ? t("speech.stop") : caption) : null}
    </Button>
  );
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      {button("normal", label ?? t("speech.listen"), mode === "normal" ? t("speech.stop") : label === undefined ? t("speech.listenTo", { text: shown }) : t("speech.listen"))}
      {slow && button("slow", t("speech.listenSlow"), mode === "slow" ? t("speech.stop") : t("speech.listenSlow"))}
      {problem === "voice" && <span role="status" className="text-xs text-slate-600">{t("speech.noVoice")}</span>}
      {problem === "error" && <span role="status" className="text-xs text-red-700">{t("speech.failed")}</span>}
    </span>
  );
}
