import { useQuery } from "@tanstack/react-query";
import { GraduationCap, Layers, ListChecks, TextCursorInput } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, type SetFilter } from "../api/client";
import { setsKey, storiesKey } from "../api/keys";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n/I18nProvider";
import { topicLabel, typeLabel } from "../i18n/labels";
import { Badge, Button, Card, ErrorText, inputCls, PageHeader, Skeleton } from "../components/ui";
import { Blanks } from "../practice/Blanks";
import { Choices, type Direction } from "../practice/Choices";
import { Flashcards } from "../practice/Flashcards";

export default function Practice() {
  const { active, info } = useActiveLanguage();
  const { user } = useAuth();
  const { t, err } = useI18n();
  const [params, setParams] = useSearchParams();
  const name = info(active)?.native ?? active;
  const storyParam = Number(params.get("story"));
  const storyId = Number.isInteger(storyParam) && storyParam > 0 ? storyParam : null;
  const [mode, setMode] = useState<"cards" | "choice" | null>(null);
  const [direction, setDirection] = useState<Direction>("meaning");
  const [setPick, setSetPick] = useState("all");                 // "all", "general" or a set id
  const sets = useQuery({ queryKey: setsKey(user!.id, active), queryFn: () => api.sets(active) });
  const filter: SetFilter = setPick === "all" || setPick === "general" ? setPick : Number(setPick);
  const stories = useQuery({ queryKey: storiesKey(user!.id, "practice-list", active), queryFn: () => api.stories({ language: active, limit: 100 }) });
  useEffect(() => { setMode(null); setSetPick("all"); }, [active]);

  const back = () => { setMode(null); setParams({}); };
  return (
    <div>
      <PageHeader title={t("nav.practice")} description={t("practice.description")} actions={<Badge tone="brand"><span lang={active}>{name}</span></Badge>} />
      {mode === "cards" ? (
        <Card><Flashcards language={active} set={filter} onDone={back} /></Card>
      ) : mode === "choice" ? (
        <Card><Choices language={active} set={filter} direction={direction} onDone={back} /></Card>
      ) : storyId !== null ? (
        <Card><Blanks storyId={storyId} onDone={back} /></Card>
      ) : (
        <>
        {(sets.data?.items.length ?? 0) > 0 && (
          <div className="mb-4 max-w-xs">
            <label htmlFor="practice-set" className="mb-1 block text-sm font-medium text-slate-700">{t("practice.set")}</label>
            <select id="practice-set" className={inputCls} value={setPick} onChange={(e) => setSetPick(e.target.value)}>
              <option value="all">{t("sets.all")}</option>
              <option value="general">{t("sets.general")}</option>
              {sets.data!.items.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
            </select>
          </div>
        )}
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
        </>
      )}
      {mode === null && storyId === null && <p className="mt-4 flex items-center gap-2 text-xs text-slate-600"><GraduationCap aria-hidden className="size-4" />{t("practice.footer")}</p>}
    </div>
  );
}
