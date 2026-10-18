import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookmarkPlus, GraduationCap, RefreshCw, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, type GeneratedStory } from "../api/client";
import { storiesKey } from "../api/keys";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { StoryReport } from "../components/StoryReport";
import { topicLabel, typeLabel } from "../i18n/labels";
import { useI18n } from "../i18n/I18nProvider";
import { Badge, Button, Card, ErrorText, inputCls, Notice, PageHeader } from "../components/ui";

const CLASSIC = ["narration", "dialogue"];          // these two have no topic

export default function Studio() {
  const { active, info } = useActiveLanguage();
  const { user } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const { t, err } = useI18n();
  const lang = info(active);
  const name = lang?.native ?? active;
  const options = useQuery({ queryKey: ["story-options"], queryFn: api.storyOptions, staleTime: Infinity });
  const [type, setType] = useState("");
  const [topic, setTopic] = useState("");
  const [story, setStory] = useState<GeneratedStory | null>(null);
  const [savedId, setSavedId] = useState<number | null>(null);
  const saved = savedId !== null;
  const generate = useMutation({ mutationFn: api.generateStory, onSuccess: (s) => { setStory(s); setSavedId(null); } });
  const save = useMutation({
    mutationFn: api.saveStory,
    onSuccess: (s) => {
      setSavedId(s.id);
      toast(t("common.savedToLibrary"));
      if (user) void qc.invalidateQueries({ queryKey: storiesKey(user.id) });
    },
  });

  useEffect(() => { setStory(null); setSavedId(null); generate.reset(); save.reset(); }, [active]);   // a story belongs to one language

  const make = () => generate.mutate({ language: active, story_type: type || undefined, topic: !type || CLASSIC.includes(type) ? undefined : topic || undefined });
  const enabled = lang?.stories_enabled !== false;
  const failure = generate.error instanceof ApiError ? generate.error : null;

  return (
    <div>
      <PageHeader
        title={t("studio.title")}
        description={t("studio.description")}
        actions={<Badge tone="brand"><span lang={active}>{name}</span></Badge>}
      />
      <Card className="space-y-4">
        {!enabled ? (
          <Notice tone="warning">{t("studio.unavailable", { language: name })}</Notice>
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="story-type" className="mb-1 block text-sm font-medium text-slate-700">{t("studio.kind")}</label>
                <select id="story-type" className={inputCls} value={type} onChange={(e) => setType(e.target.value)}>
                  <option value="">{t("studio.surprise")}</option>
                  {options.data?.types.map((ty) => <option key={ty} value={ty}>{typeLabel(t, ty)}</option>)}
                </select>
              </div>
              <div>
                <label htmlFor="story-topic" className="mb-1 block text-sm font-medium text-slate-700">{t("studio.topic")}</label>
                <select id="story-topic" className={inputCls} value={topic} onChange={(e) => setTopic(e.target.value)} disabled={!type || CLASSIC.includes(type)}>
                  <option value="">{t("studio.anyTopic")}</option>
                  {options.data?.topics.map((tp) => <option key={tp} value={tp}>{topicLabel(t, tp)}</option>)}
                </select>
                {(!type || CLASSIC.includes(type)) && <p className="mt-1 text-xs text-slate-600">{t("studio.topicHint")}</p>}
              </div>
            </div>
            <div>
              <Button onClick={make} loading={generate.isPending} icon={<Sparkles aria-hidden className="size-4" />}>
                {generate.isPending ? t("studio.writing") : t("studio.make")}
              </Button>
              {generate.isPending && <p role="status" className="mt-2 text-sm text-slate-600">{t("studio.wait")}</p>}
              {failure && (
                <ErrorText>
                  {err(failure)}
                  {failure.code === "not_enough_words" && <> <Link to="/vocabulary" className="font-medium underline">{t("studio.goVocab")}</Link>.</>}
                </ErrorText>
              )}
              {generate.error && !failure && <ErrorText>{err(generate.error)}</ErrorText>}
            </div>
          </>
        )}
      </Card>

      {story && (
        <Card className="mt-4 space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge>{typeLabel(t, story.story_type ?? "story")}</Badge>
            {story.topic && <Badge>{topicLabel(t, story.topic)}</Badge>}
            <span className="text-xs text-slate-600">{t("studio.builtFrom", { used: story.words_used, total: story.words_total })}</span>
          </div>
          <p lang={story.language} className="whitespace-pre-wrap break-words text-base leading-relaxed text-slate-900">{story.story}</p>
          <StoryReport report={story.report} languageName={name} />
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              onClick={() => save.mutate({ language: story.language, body: story.story, story_type: story.story_type, topic: story.topic })}
              disabled={saved}
              loading={save.isPending}
              icon={<BookmarkPlus aria-hidden className="size-4" />}
            >
              {saved ? t("chat.saved") : t("studio.save")}
            </Button>
            {saved && (
              <Link to={`/practice?story=${savedId}`} className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-surface px-3.5 py-2 text-sm font-medium text-slate-700 shadow-xs hover:bg-slate-100/70">
                <GraduationCap aria-hidden className="size-4" />{t("studio.practice")}
              </Link>
            )}
            <Button variant="ghost" onClick={make} disabled={generate.isPending} icon={<RefreshCw aria-hidden className="size-4" />}>{t("studio.another")}</Button>
          </div>
          {save.error && <ErrorText>{err(save.error, "common.saveFailed")}</ErrorText>}
        </Card>
      )}
    </div>
  );
}
