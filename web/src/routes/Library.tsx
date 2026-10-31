import { BookOpen } from "lucide-react";
import { Link } from "react-router-dom";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { Badge, Card, EmptyState, ErrorText, PageHeader, Skeleton } from "../components/ui";
import { useI18n } from "../i18n/I18nProvider";
import { Pager } from "../components/Pager";
import { StoryRow } from "../library/StoryRow";
import { LIMIT, useLibrary } from "../library/useLibrary";

/** The learner's saved stories, ten to a page. The row, the opened story, the pager and the paging/deleting logic are in library/. */
export default function Library() {
  const { active, info } = useActiveLanguage();
  const { t, err } = useI18n();
  const name = info(active)?.native ?? active;
  const { list, total, offset, setOffset, openId, toggle, remove, ask } = useLibrary(active);

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
              <StoryRow key={s.id} story={s} languageName={name} open={openId === s.id} onToggle={() => toggle(s.id)}
                onDelete={() => void ask(s)} deleting={remove.isPending && remove.variables === s.id} />
            ))}
          </ul>
        )}
        {remove.error && <div className="px-5 pb-4"><ErrorText>{err(remove.error)}</ErrorText></div>}
        <Pager offset={offset} limit={LIMIT} total={total} onOffset={setOffset} />
      </Card>
    </div>
  );
}
