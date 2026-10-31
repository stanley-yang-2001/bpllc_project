import { BookOpen, GraduationCap, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import type { StoryCard } from "../api/client";
import { StoryMeta } from "../components/StoryMeta";
import { Badge, Button } from "../components/ui";
import { useI18n } from "../i18n/I18nProvider";
import { OpenedStory } from "./OpenedStory";

const when = (iso: string, locale: string) => new Date(iso).toLocaleDateString(locale, { day: "numeric", month: "short", year: "numeric" });

/** One saved story in the list: its badges, a two-line preview or the opened story, and Open / Practise / Delete. */
export function StoryRow({ story, languageName, open, onToggle, onDelete, deleting }: {
  story: StoryCard; languageName: string; open: boolean; onToggle: () => void; onDelete: () => void; deleting: boolean;
}) {
  const { t, locale } = useI18n();
  return (
    <li className="py-4">
      <div className="flex flex-wrap items-center gap-2">
        <StoryMeta kind={story.story_type} topic={story.topic} difficulty={story.difficulty} />
        <Badge tone={story.passed ? "good" : "accent"}>{story.passed ? t("common.looksGood") : t("common.needsLook")}</Badge>
        <span className="text-xs text-slate-600">{when(story.created_at, locale)}</span>
      </div>
      {!open && <p lang={story.language} className="mt-2 line-clamp-2 whitespace-pre-line text-sm text-slate-700">{story.body}</p>}
      {open && <OpenedStory id={story.id} languageName={languageName} />}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button variant="secondary" onClick={onToggle} aria-expanded={open} icon={<BookOpen aria-hidden className="size-4" />}>{open ? t("common.close") : t("common.open")}</Button>
        <Link to={`/practice?story=${story.id}`} className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-surface px-3.5 py-2 text-sm font-medium text-slate-700 shadow-xs hover:bg-slate-100/70">
          <GraduationCap aria-hidden className="size-4" />{t("studio.practice")}
        </Link>
        <Button variant="ghost" onClick={onDelete} loading={deleting} icon={<Trash2 aria-hidden className="size-4" />} aria-label={t("library.deleteAria")}>{t("common.delete")}</Button>
      </div>
    </li>
  );
}
