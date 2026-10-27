import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, ChevronLeft, ChevronRight, GraduationCap, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type StoryCard } from "../api/client";
import { storiesKey } from "../api/keys";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { useAuth } from "../auth/AuthContext";
import { useConfirm } from "../components/Confirm";
import { StoryReport } from "../components/StoryReport";
import { StoryTools } from "../text/StoryTools";
import { useToast } from "../components/Toast";
import { useI18n } from "../i18n/I18nProvider";
import { diffLabel, topicLabel, typeLabel } from "../i18n/labels";
import { Badge, Button, Card, EmptyState, ErrorText, PageHeader, Skeleton } from "../components/ui";

const LIMIT = 10;
const when = (iso: string, locale: string) => new Date(iso).toLocaleDateString(locale, { day: "numeric", month: "short", year: "numeric" });

function Opened({ id, languageName }: { id: number; languageName: string }) {
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

function Row({ story, languageName, open, onToggle, onDelete, deleting }: {
  story: StoryCard; languageName: string; open: boolean; onToggle: () => void; onDelete: () => void; deleting: boolean;
}) {
  const { t, locale } = useI18n();
  return (
    <li className="py-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge>{story.story_type ? typeLabel(t, story.story_type) : t("library.fromChat")}</Badge>
        {story.topic && <Badge>{topicLabel(t, story.topic)}</Badge>}
        {story.difficulty && <Badge>{diffLabel(t, story.difficulty)}</Badge>}
        <Badge tone={story.passed ? "good" : "accent"}>{story.passed ? t("common.looksGood") : t("common.needsLook")}</Badge>
        <span className="text-xs text-slate-600">{when(story.created_at, locale)}</span>
      </div>
      {!open && <p lang={story.language} className="mt-2 line-clamp-2 whitespace-pre-line text-sm text-slate-700">{story.body}</p>}
      {open && <Opened id={story.id} languageName={languageName} />}
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

export default function Library() {
  const { active, info } = useActiveLanguage();
  const { user } = useAuth();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const toast = useToast();
  const { t, err } = useI18n();
  const name = info(active)?.native ?? active;
  // The page position belongs to one language, so it is derived rather than reset in an effect: an effect would let one
  // request go out for the new language at the old language's offset.
  const [place, setPlace] = useState({ language: active, offset: 0 });
  const offset = place.language === active ? place.offset : 0;
  const setOffset = (n: number) => setPlace({ language: active, offset: n });
  const [openId, setOpenId] = useState<number | null>(null);
  useEffect(() => { setOpenId(null); }, [active]);

  const list = useQuery({
    queryKey: storiesKey(user!.id, "list", active, offset),
    queryFn: () => api.stories({ language: active, limit: LIMIT, offset }),
    placeholderData: keepPreviousData,
  });
  const remove = useMutation({
    mutationFn: api.deleteStory,
    onSuccess: (_, id) => {
      if (openId === id) setOpenId(null);
      toast(t("library.deleted"));
      void qc.invalidateQueries({ queryKey: storiesKey(user!.id) });
    },
  });
  const total = list.data?.total ?? 0;
  useEffect(() => { if (list.data && list.data.items.length === 0 && offset > 0) setOffset(Math.max(0, offset - LIMIT)); }, [list.data, offset]);   // the last story on a page was deleted

  const ask = async (s: StoryCard) => {
    if (await confirm({ title: t("library.deleteTitle"), body: t("library.deleteBody"), confirmLabel: t("library.deleteConfirm") })) remove.mutate(s.id);
  };

  return (
    <div>
      <PageHeader title={t("nav.library")} description={t("library.description")} actions={<Badge tone="brand"><span lang={active}>{name}</span></Badge>} />
      <Card className="p-0">
        {list.isPending ? (
          <div className="space-y-4 p-5"><Skeleton className="h-16 w-full" /><Skeleton className="h-16 w-full" /></div>
        ) : list.isError ? (
          <div className="p-5"><ErrorText>{err(list.error)}</ErrorText></div>
        ) : total === 0 ? (
          <EmptyState icon={<BookOpen aria-hidden className="size-5" />} title={t("library.empty.title", { language: name })}
            action={<Link to="/studio" className="text-sm font-medium text-brand-600 underline dark:text-brand-200">{t("library.empty.action")}</Link>}>
            {t("library.empty.body")}
          </EmptyState>
        ) : (
          <ul className="divide-y divide-slate-100 px-5">
            {list.data.items.map((s) => (
              <Row key={s.id} story={s} languageName={name} open={openId === s.id} onToggle={() => setOpenId(openId === s.id ? null : s.id)}
                onDelete={() => void ask(s)} deleting={remove.isPending && remove.variables === s.id} />
            ))}
          </ul>
        )}
        {remove.error && <div className="px-5 pb-4"><ErrorText>{err(remove.error)}</ErrorText></div>}
        {total > LIMIT && (
          <div className="flex items-center justify-between border-t border-slate-200 p-3 text-sm text-slate-600">
            <Button variant="ghost" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMIT))} icon={<ChevronLeft aria-hidden className="size-4" />}>{t("common.previous")}</Button>
            <Badge>{t("common.range", { from: offset + 1, to: Math.min(offset + LIMIT, total), total })}</Badge>
            <Button variant="ghost" disabled={offset + LIMIT >= total} onClick={() => setOffset(offset + LIMIT)}>{t("common.next")}<ChevronRight aria-hidden className="size-4" /></Button>
          </div>
        )}
      </Card>
    </div>
  );
}
