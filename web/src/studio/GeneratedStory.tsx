import { BookmarkPlus, GraduationCap, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";
import { StoryReport } from "../components/StoryReport";
import { Badge, Button, Card, ErrorText } from "../components/ui";
import { useI18n } from "../i18n/I18nProvider";
import { diffLabel, topicLabel, typeLabel } from "../i18n/labels";
import { StoryTools } from "../text/StoryTools";
import { ownModelName, requestedOf } from "./labels";
import type { StoryGeneration } from "./useStoryGeneration";

/** The story that was just made: the text, its tools and report, and Save, Practise and Another. */
export function GeneratedStory({ g, languageName, onAnother }: { g: StoryGeneration; languageName: string; onAnother: () => void }) {
  const { t, err } = useI18n();
  const { story, saved, savedId, save, generate } = g;
  if (!story) return null;
  const requested = requestedOf(story.report);
  return (
    <Card className="mt-4 space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge>{typeLabel(t, story.story_type ?? "story")}</Badge>
        {story.topic && <Badge>{topicLabel(t, story.topic)}</Badge>}
        {requested.difficulty && <Badge>{diffLabel(t, requested.difficulty)}</Badge>}
        <span className="text-xs text-slate-600">{t("studio.builtFrom", { used: story.words_used, total: story.words_total })}</span>
      </div>
      <p lang={story.language} className="whitespace-pre-wrap break-words text-base leading-relaxed text-slate-900">{story.story}</p>
      <StoryTools text={story.story} language={story.language} id="studio" />
      <StoryReport report={story.report} languageName={languageName} />
      <div className="flex flex-wrap gap-2">
        <Button
          variant="secondary"
          onClick={() => save.mutate({ language: story.language, body: story.story, story_type: story.story_type, topic: story.topic, ...requested, ...(ownModelName(story.report) ? { model: ownModelName(story.report) } : {}) })}
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
        <Button variant="ghost" onClick={onAnother} disabled={generate.isPending} icon={<RefreshCw aria-hidden className="size-4" />}>{t("studio.another")}</Button>
      </div>
      {save.error && <ErrorText>{err(save.error, "common.saveFailed")}</ErrorText>}
    </Card>
  );
}
