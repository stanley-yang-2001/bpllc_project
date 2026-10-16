import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookmarkPlus, RefreshCw, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, type GeneratedStory } from "../api/client";
import { storiesKey } from "../api/keys";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { StoryReport } from "../components/StoryReport";
import { Badge, Button, Card, ErrorText, inputCls, Notice, PageHeader } from "../components/ui";

const CLASSIC = ["narration", "dialogue"];          // these two have no topic
const label = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);

export default function Studio() {
  const { active, info } = useActiveLanguage();
  const { user } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const lang = info(active);
  const name = lang?.name ?? active;
  const options = useQuery({ queryKey: ["story-options"], queryFn: api.storyOptions, staleTime: Infinity });
  const [type, setType] = useState("");
  const [topic, setTopic] = useState("");
  const [story, setStory] = useState<GeneratedStory | null>(null);
  const [saved, setSaved] = useState(false);
  const generate = useMutation({ mutationFn: api.generateStory, onSuccess: (s) => { setStory(s); setSaved(false); } });
  const save = useMutation({
    mutationFn: api.saveStory,
    onSuccess: () => {
      setSaved(true);
      toast("Saved to your library");
      if (user) void qc.invalidateQueries({ queryKey: storiesKey(user.id) });
    },
  });

  useEffect(() => { setStory(null); setSaved(false); generate.reset(); save.reset(); }, [active]);   // a story belongs to one language

  const make = () => generate.mutate({ language: active, story_type: type || undefined, topic: !type || CLASSIC.includes(type) ? undefined : topic || undefined });
  const enabled = lang?.stories_enabled !== false;
  const failure = generate.error instanceof ApiError ? generate.error : null;

  return (
    <div>
      <PageHeader
        title="Story Studio"
        description="Make a short story from the words on your list, and see how well it fits them."
        actions={<Badge tone="brand">{name}</Badge>}
      />
      <Card className="space-y-4">
        {!enabled ? (
          <Notice tone="warning">Stories in {name} are not available yet.</Notice>
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="story-type" className="mb-1 block text-sm font-medium text-slate-700">Kind of story</label>
                <select id="story-type" className={inputCls} value={type} onChange={(e) => setType(e.target.value)}>
                  <option value="">Surprise me</option>
                  {options.data?.types.map((t) => <option key={t} value={t}>{label(t)}</option>)}
                </select>
              </div>
              <div>
                <label htmlFor="story-topic" className="mb-1 block text-sm font-medium text-slate-700">Topic</label>
                <select id="story-topic" className={inputCls} value={topic} onChange={(e) => setTopic(e.target.value)} disabled={!type || CLASSIC.includes(type)}>
                  <option value="">Any topic</option>
                  {options.data?.topics.map((t) => <option key={t} value={t}>{label(t)}</option>)}
                </select>
                {(!type || CLASSIC.includes(type)) && <p className="mt-1 text-xs text-slate-600">Topics are for the newer kinds of story. Pick one of those to choose a topic.</p>}
              </div>
            </div>
            <div>
              <Button onClick={make} loading={generate.isPending} icon={<Sparkles aria-hidden className="size-4" />}>
                {generate.isPending ? "Writing…" : "Make a story"}
              </Button>
              {generate.isPending && <p role="status" className="mt-2 text-sm text-slate-600">Stories can take up to a minute.</p>}
              {failure && (
                <ErrorText>
                  {failure.message}
                  {failure.code === "not_enough_words" && <> <Link to="/vocabulary" className="font-medium underline">Go to your vocabulary</Link>.</>}
                </ErrorText>
              )}
              {generate.error && !failure && <ErrorText>Something went wrong. Please try again.</ErrorText>}
            </div>
          </>
        )}
      </Card>

      {story && (
        <Card className="mt-4 space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge>{label(story.story_type ?? "story")}</Badge>
            {story.topic && <Badge>{label(story.topic)}</Badge>}
            <span className="text-xs text-slate-600">Built from {story.words_used} of your {story.words_total} words</span>
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
              {saved ? "Saved" : "Save to library"}
            </Button>
            <Button variant="ghost" onClick={make} disabled={generate.isPending} icon={<RefreshCw aria-hidden className="size-4" />}>Make another</Button>
          </div>
          {save.error && <ErrorText>{save.error instanceof ApiError ? save.error.message : "Couldn't save. Please try again."}</ErrorText>}
        </Card>
      )}
    </div>
  );
}
