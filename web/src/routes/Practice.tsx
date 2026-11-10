import { useQuery } from "@tanstack/react-query";
import { GraduationCap, Headphones, Layers, ListChecks, Tags, TextCursorInput } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { progressKey, storiesKey } from "../api/keys";
import type { FlashcardScope } from "../api/types";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n/I18nProvider";
import { topicLabel, typeLabel } from "../i18n/labels";
import { Badge, Button, Card, ErrorText, inputCls, PageHeader, Skeleton } from "../components/ui";
import { Blanks } from "../practice/Blanks";
import { Choices, type Direction } from "../practice/Choices";
import { Dictation } from "../practice/Dictation";
import { Flashcards } from "../practice/Flashcards";
import { PosPractice } from "../practice/PosPractice";
import { ProgressCard } from "../practice/ProgressCard";
import { pickedToFilter, SetPicker } from "../practice/SetPicker";
import { StudyStats } from "../practice/StudyStats";
import { speechSupported, voiceFor } from "../speech/speak";
import { useVoices } from "../speech/useVoices";

const MINUTE_CHOICES = [2, 5, 10, 20, 30];
const MINUTES_KEY = "tutor.cards.minutes";
const DEFAULT_MINUTES = 10;
/** The session length the learner chose last time (0 = no limit), or 10 minutes. */
function storedMinutes(): number | null {
  try {
    const v = localStorage.getItem(MINUTES_KEY);
    if (v === null) return DEFAULT_MINUTES;
    const n = Number(v);
    return n === 0 ? null : MINUTE_CHOICES.includes(n) ? n : DEFAULT_MINUTES;
  } catch { return DEFAULT_MINUTES; }
}

export default function Practice() {
  const { active, info } = useActiveLanguage();
  const { user } = useAuth();
  const { t, err } = useI18n();
  const [params, setParams] = useSearchParams();
  const name = info(active)?.native ?? active;
  useVoices();                                                      // re-render when the device finishes loading its voices
  const canSpeak = speechSupported();
  const noVoice = canSpeak && voiceFor(active) === null;            // the device lists voices but none fit this language (undefined = not loaded yet)
  const storyParam = Number(params.get("story"));
  const storyId = Number.isInteger(storyParam) && storyParam > 0 ? storyParam : null;
  const [mode, setMode] = useState<"cards" | "choice" | "dictation" | "pos" | null>(null);
  const [direction, setDirection] = useState<Direction>("meaning");
  const [picked, setPicked] = useState<string[]>([]);          // the sets chosen ("general" or a set id); none = every word
  const [cardScope, setCardScope] = useState<FlashcardScope>("due");
  const [cardIds, setCardIds] = useState<number[]>([]);
  const [minutes, setMinutes] = useState<number | null>(storedMinutes);    // how long a flashcard session lasts; null = until the words run out
  const chooseMinutes = (m: number | null) => { setMinutes(m); try { localStorage.setItem(MINUTES_KEY, String(m ?? 0)); } catch { /* not kept */ } };          // for scope "ids": exactly these words
  const [dueOnly, setDueOnly] = useState(false);                 // only words that are due for review (then never-practised ones)
  const filter = pickedToFilter(picked);
  const progress = useQuery({ queryKey: [...progressKey(user!.id, active), String(filter)], queryFn: () => api.practiceProgress(active, filter) });
  const stories = useQuery({ queryKey: storiesKey(user!.id, "practice-list", active), queryFn: () => api.stories({ language: active, limit: 100 }) });
  useEffect(() => { setMode(null); setPicked([]); setDueOnly(false); }, [active]);

  const back = () => { setMode(null); setParams({}); };
  const study = (scope: FlashcardScope, ids: number[] = []) => { setCardScope(scope); setCardIds(ids); setMode("cards"); };
  const p = progress.data;
  const wordCount = p ? p.new + p.learning + p.known : 0;
  return (
    <div>
      <PageHeader title={t("nav.practice")} description={t("practice.description")} actions={<Badge tone="brand"><span lang={active}>{name}</span></Badge>} />
      {mode === "cards" ? (
        <Card><Flashcards language={active} set={filter} scope={cardScope} ids={cardIds} minutes={minutes} onDone={back} onPractise={(ids) => study("ids", ids)} /></Card>
      ) : mode === "pos" ? (
        <Card><PosPractice language={active} set={filter} due={dueOnly} onDone={back} /></Card>
      ) : mode === "dictation" ? (
        <Card><Dictation language={active} set={filter} due={dueOnly} onDone={back} /></Card>
      ) : mode === "choice" ? (
        <Card><Choices language={active} set={filter} direction={direction} due={dueOnly} onDone={back} /></Card>
      ) : storyId !== null ? (
        <Card><Blanks storyId={storyId} onDone={back} /></Card>
      ) : (
        <>
        <SetPicker language={active} picked={picked} onChange={setPicked} />
        <ProgressCard language={active} set={filter} onReview={() => study("due")} />
        <StudyStats language={active} set={filter} onPractise={(ids) => study("ids", ids)} />
        <label className="mb-4 flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={dueOnly} onChange={(e) => setDueOnly(e.target.checked)} />{t("practice.dueOnly")}
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <Card className="space-y-3">
            <h2 className="flex items-center gap-2 font-semibold text-slate-900"><ListChecks aria-hidden className="size-5" />{t("practice.choice.title")}</h2>
            <p className="text-sm text-slate-600">{t("practice.choice.text")}</p>
            <div>
              <label htmlFor="practice-direction" className="mb-1 block text-sm font-medium text-slate-700">{t("practice.choice.direction")}</label>
              <select id="practice-direction" className={inputCls} value={direction} onChange={(e) => setDirection(e.target.value as Direction)}>
                <option value="meaning">{t("practice.choice.dirMeaning")}</option>
                <option value="word">{t("practice.choice.dirWord")}</option>
              </select>
            </div>
            <Button onClick={() => setMode("choice")}>{t("practice.choice.start")}</Button>
          </Card>
          <Card className="space-y-3">
            <h2 className="flex items-center gap-2 font-semibold text-slate-900"><Layers aria-hidden className="size-5" />{t("practice.flashcards.title")}</h2>
            <p className="text-sm text-slate-600">{t("practice.cards.text", { language: name })}</p>
            {p && <p className="text-xs text-slate-600">{t("practice.cards.counts", { due: p.due, new: p.new, n: wordCount })}</p>}
            <div className="flex flex-wrap items-center gap-2" role="group" aria-label={t("practice.cards.length")}>
              <span className="text-sm text-slate-700">{t("practice.cards.length")}</span>
              {[...MINUTE_CHOICES, null].map((m) => (
                <button key={m ?? "none"} type="button" aria-pressed={minutes === m} onClick={() => chooseMinutes(m)}
                  className={`rounded-full border px-3 py-1 text-sm ${minutes === m ? "border-brand-600 bg-brand-600 text-white" : "border-slate-300 bg-surface text-slate-700 hover:bg-slate-100/70"}`}>
                  {m === null ? t("practice.cards.noLimit") : t("practice.stats.minutes", { n: m })}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => study("due")}>{t("practice.cards.studyDue")}</Button>
              <Button variant="secondary" onClick={() => study("all")}>{t("practice.cards.studyAll", { n: wordCount })}</Button>
            </div>
          </Card>
          <Card className="space-y-3">
            <h2 className="flex items-center gap-2 font-semibold text-slate-900"><Tags aria-hidden className="size-5" />{t("practice.pos.title")}</h2>
            <p className="text-sm text-slate-600">{t("practice.pos.text")}</p>
            <Button onClick={() => setMode("pos")}>{t("practice.pos.start")}</Button>
          </Card>
          <Card className="space-y-3">
            <h2 className="flex items-center gap-2 font-semibold text-slate-900"><Headphones aria-hidden className="size-5" />{t("practice.dictation.title")}</h2>
            <p className="text-sm text-slate-600">{t("practice.dictation.text")}</p>
            {!canSpeak || noVoice
              ? <p role="status" className="text-sm text-slate-600">{canSpeak ? t("practice.dictation.noVoice", { language: name }) : t("practice.dictation.noSpeech")}</p>
              : <Button onClick={() => setMode("dictation")}>{t("practice.dictation.start")}</Button>}
          </Card>
          <Card className="space-y-3">
            <h2 className="flex items-center gap-2 font-semibold text-slate-900"><TextCursorInput aria-hidden className="size-5" />{t("practice.cloze.title")}</h2>
            <p className="text-sm text-slate-600">{t("practice.cloze.text")}</p>
            {stories.isPending ? <Skeleton className="h-9 w-full" /> : stories.isError ? <ErrorText>{err(stories.error)}</ErrorText> : stories.data.items.length === 0 ? (
              <p className="text-sm text-slate-600">{t("practice.cloze.noStories", { language: name })} <Link to="/studio" className="font-medium text-brand-600 underline dark:text-brand-200">{t("practice.cloze.makeOne")}</Link></p>
            ) : (
              <div>
                <label htmlFor="practice-story" className="mb-1 block text-sm font-medium text-slate-700">{t("practice.cloze.story")}</label>
                <select id="practice-story" className={inputCls} defaultValue="" onChange={(e) => e.target.value && setParams({ story: e.target.value })}>
                  <option value="">{t("practice.cloze.choose")}</option>
                  {stories.data.items.map((s) => (
                    <option key={s.id} value={s.id}>{(s.topic ? topicLabel(t, s.topic) : s.story_type ? typeLabel(t, s.story_type) : t("practice.cloze.chatStory"))} · {s.body.split("\n")[0].slice(0, 40)}</option>
                  ))}
                </select>
              </div>
            )}
          </Card>
        </div>
        </>
      )}
      {mode === null && storyId === null && <p className="mt-4 flex items-center gap-2 text-xs text-slate-600"><GraduationCap aria-hidden className="size-4" />{t("practice.footer")}</p>}
    </div>
  );
}
