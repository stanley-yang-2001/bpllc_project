import { useQuery } from "@tanstack/react-query";
import { TextCursorInput } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import { storiesKey } from "../../api/keys";
import { useAuth } from "../../auth/AuthContext";
import { useI18n } from "../../i18n/I18nProvider";
import { topicLabel, typeLabel } from "../../i18n/labels";
import { ErrorText, inputCls, Skeleton } from "../../components/ui";
import { Blanks } from "../Blanks";
import { ModeTile } from "./ModeTile";
import type { PracticeMode } from "./types";

export const ClozeMode: PracticeMode<"cloze"> = {
  Tile({ ctx, start }) {
    const { user } = useAuth();
    const { t, err } = useI18n();
    const stories = useQuery({ queryKey: storiesKey(user!.id, "practice-list", ctx.language), queryFn: () => api.stories({ language: ctx.language, limit: 100 }) });
    return (
      <ModeTile icon={TextCursorInput} title={t("practice.cloze.title")} text={t("practice.cloze.text")}>
        {stories.isPending ? <Skeleton className="h-9 w-full" /> : stories.isError ? <ErrorText>{err(stories.error)}</ErrorText> : stories.data.items.length === 0 ? (
          <p className="text-sm text-slate-600">{t("practice.cloze.noStories", { language: ctx.name })} <Link to="/studio" className="font-medium text-brand-600 underline dark:text-brand-200">{t("practice.cloze.makeOne")}</Link></p>
        ) : (
          <div>
            <label htmlFor="practice-story" className="mb-1 block text-sm font-medium text-slate-700">{t("practice.cloze.story")}</label>
            <select id="practice-story" className={inputCls} defaultValue="" onChange={(e) => e.target.value && start({ mode: "cloze", storyId: Number(e.target.value) })}>
              <option value="">{t("practice.cloze.choose")}</option>
              {stories.data.items.map((s) => (
                <option key={s.id} value={s.id}>{(s.topic ? topicLabel(t, s.topic) : s.story_type ? typeLabel(t, s.story_type) : t("practice.cloze.chatStory"))} · {s.body.split("\n")[0].slice(0, 40)}</option>
              ))}
            </select>
          </div>
        )}
      </ModeTile>
    );
  },
  Session: ({ launch, onDone }) => <Blanks storyId={launch.storyId} onDone={onDone} />,
};
