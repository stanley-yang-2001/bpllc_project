import { useQuery } from "@tanstack/react-query";
import { Check, GraduationCap, Layers, RotateCcw, TextCursorInput, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, type ClozeItem } from "../api/client";
import { storiesKey } from "../api/keys";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n/I18nProvider";
import { topicLabel, typeLabel } from "../i18n/labels";
import { Badge, Button, Card, EmptyState, ErrorText, inputCls, PageHeader, Skeleton } from "../components/ui";

const CARDS = 10;

/** Nothing here is stored: a score is shown and forgotten (design: practice results are not stored). `round` makes a
 * fresh shuffle each time the learner starts again; the cache is dropped as soon as the page is left. */
function Flashcards({ language, onDone }: { language: string; onDone: () => void }) {
  const { user } = useAuth();
  const { t, err } = useI18n();
  const [round, setRound] = useState(0);
  const cards = useQuery({ queryKey: ["practice", user!.id, "flashcards", language, round], queryFn: () => api.flashcards({ language, limit: CARDS }), gcTime: 0, staleTime: Infinity });
  const [index, setIndex] = useState(0);
  const [shown, setShown] = useState(false);
  const [known, setKnown] = useState(0);
  const again = () => { setRound((r) => r + 1); setIndex(0); setShown(false); setKnown(0); };

  if (cards.isPending) return <Skeleton className="h-40 w-full" />;
  if (cards.isError) return <ErrorText>{err(cards.error)}</ErrorText>;
  const items = cards.data.items;
  if (items.length === 0)
    return (
      <EmptyState icon={<Layers aria-hidden className="size-5" />} title={t("practice.flashcards.noneTitle")}
        action={<Link to="/vocabulary" className="text-sm font-medium text-brand-600 underline dark:text-brand-200">{t("practice.flashcards.addMeanings")}</Link>}>
        {t("practice.flashcards.noneBody")}
      </EmptyState>
    );
  if (index >= items.length)
    return (
      <div className="space-y-3 text-center" role="status">
        <p className="text-lg font-semibold text-slate-900">{t("practice.flashcards.score", { known, total: items.length })}</p>
        <div className="flex justify-center gap-2">
          <Button onClick={again} icon={<RotateCcw aria-hidden className="size-4" />}>{t("practice.again")}</Button>
          <Button variant="secondary" onClick={onDone}>{t("common.back")}</Button>
        </div>
      </div>
    );
  const card = items[index];
  const next = (knew: boolean) => { if (knew) setKnown(known + 1); setShown(false); setIndex(index + 1); };
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">{t("practice.cardOf", { n: index + 1, total: items.length })}</p>
      <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-8 text-center dark:bg-slate-100/40">
        <p lang={language} className="text-2xl font-semibold text-slate-900">{card.word}</p>
        {shown && <p className="mt-3 text-base text-slate-700">{card.meaning}</p>}
      </div>
      {!shown ? (
        <Button onClick={() => setShown(true)}>{t("practice.showMeaning")}</Button>
      ) : (
        <div className="flex gap-2">
          <Button onClick={() => next(true)} icon={<Check aria-hidden className="size-4" />}>{t("practice.knewIt")}</Button>
          <Button variant="secondary" onClick={() => next(false)} icon={<X aria-hidden className="size-4" />}>{t("practice.notYet")}</Button>
        </div>
      )}
    </div>
  );
}

function Blanks({ storyId, onDone }: { storyId: number; onDone: () => void }) {
  const { user } = useAuth();
  const { t, err } = useI18n();
  const set = useQuery({ queryKey: ["practice", user!.id, "cloze", storyId], queryFn: () => api.cloze(storyId), gcTime: 0, staleTime: Infinity });
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [right, setRight] = useState(0);
  useEffect(() => { setIndex(0); setPicked(null); setRight(0); }, [storyId]);

  if (set.isPending) return <Skeleton className="h-40 w-full" />;
  if (set.isError) return <ErrorText>{err(set.error)}</ErrorText>;
  const items: ClozeItem[] = set.data.items;
  if (index >= items.length)
    return (
      <div className="space-y-3 text-center" role="status">
        <p className="text-lg font-semibold text-slate-900">{t("practice.cloze.score", { right, total: items.length })}</p>
        <div className="flex justify-center gap-2">
          <Button onClick={() => { setIndex(0); setPicked(null); setRight(0); }} icon={<RotateCcw aria-hidden className="size-4" />}>{t("common.tryAgain")}</Button>
          <Button variant="secondary" onClick={onDone}>{t("common.back")}</Button>
        </div>
      </div>
    );
  const item = items[index];
  const choose = (choice: string) => {
    if (picked !== null) return;
    setPicked(choice);
    if (choice === item.answer) setRight(right + 1);
  };
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
        <div className="space-y-2" role="status">
          <p className={picked === item.answer ? "font-medium text-emerald-700 dark:text-emerald-400" : "font-medium text-red-700 dark:text-red-400"}>
            {picked === item.answer ? t("practice.cloze.correct") : t("practice.cloze.wrong", { answer: item.answer })}
          </p>
          <Button onClick={() => { setPicked(null); setIndex(index + 1); }}>{index + 1 === items.length ? t("practice.cloze.seeResult") : t("common.next")}</Button>
        </div>
      )}
    </div>
  );
}

export default function Practice() {
  const { active, info } = useActiveLanguage();
  const { user } = useAuth();
  const { t, err } = useI18n();
  const [params, setParams] = useSearchParams();
  const name = info(active)?.native ?? active;
  const storyParam = Number(params.get("story"));
  const storyId = Number.isInteger(storyParam) && storyParam > 0 ? storyParam : null;
  const [mode, setMode] = useState<"cards" | null>(null);
  const stories = useQuery({ queryKey: storiesKey(user!.id, "practice-list", active), queryFn: () => api.stories({ language: active, limit: 100 }) });
  useEffect(() => { setMode(null); }, [active]);

  const back = () => { setMode(null); setParams({}); };
  return (
    <div>
      <PageHeader title={t("nav.practice")} description={t("practice.description")} actions={<Badge tone="brand"><span lang={active}>{name}</span></Badge>} />
      {mode === "cards" ? (
        <Card><Flashcards language={active} onDone={back} /></Card>
      ) : storyId !== null ? (
        <Card><Blanks storyId={storyId} onDone={back} /></Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          <Card className="space-y-3">
            <h2 className="flex items-center gap-2 font-semibold text-slate-900"><Layers aria-hidden className="size-5" />{t("practice.flashcards.title")}</h2>
            <p className="text-sm text-slate-600">{t("practice.flashcards.text", { language: name })}</p>
            <Button onClick={() => setMode("cards")}>{t("practice.flashcards.start")}</Button>
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
      )}
      {mode === null && storyId === null && <p className="mt-4 flex items-center gap-2 text-xs text-slate-600"><GraduationCap aria-hidden className="size-4" />{t("practice.footer")}</p>}
    </div>
  );
}
