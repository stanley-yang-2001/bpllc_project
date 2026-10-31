import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { storiesKey } from "../api/keys";
import { useAuth } from "../auth/AuthContext";
import { StoryReport } from "../components/StoryReport";
import { ErrorText, Skeleton } from "../components/ui";
import { useI18n } from "../i18n/I18nProvider";
import { StoryTools } from "../text/StoryTools";

/** A saved story opened in the list: the whole text, its tools and its quality report, fetched when opened. */
export function OpenedStory({ id, languageName }: { id: number; languageName: string }) {
  const { user } = useAuth();
  const { err } = useI18n();
  const story = useQuery({ queryKey: storiesKey(user!.id, "one", id), queryFn: () => api.story(id) });
  if (story.isPending) return <Skeleton className="mt-3 h-24 w-full" />;
  if (story.isError) return <ErrorText>{err(story.error)}</ErrorText>;
  return (
    <div className="mt-3 space-y-3">
      <p lang={story.data.language} className="whitespace-pre-wrap break-words text-base leading-relaxed text-slate-900">{story.data.body}</p>
      <StoryTools text={story.data.body} language={story.data.language} id={`library-${id}`} />
      <StoryReport report={story.data.report} languageName={languageName} />
    </div>
  );
}
