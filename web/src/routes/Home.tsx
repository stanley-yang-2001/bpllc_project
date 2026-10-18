import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BookOpen, Layers, Library, MessageCircle, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { wordsKey } from "../api/keys";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n/I18nProvider";
import type { MessageKey } from "../i18n/messages";
import { Button, Card, PageHeader, Skeleton } from "../components/ui";

const actions = [
  { to: "/vocabulary", title: "nav.vocabulary", text: "home.vocabulary.text", icon: BookOpen },
  { to: "/chat", title: "nav.chat", text: "home.chat.text", icon: MessageCircle },
  { to: "/studio", title: "studio.title", text: "home.studio.text", icon: Sparkles },
  { to: "/practice", title: "nav.practice", text: "home.practice.text", icon: Layers },
  { to: "/library", title: "nav.library", text: "home.library.text", icon: Library },
] as const satisfies readonly { to: string; title: MessageKey; text: MessageKey; icon: unknown }[];

export default function Home() {
  const { user } = useAuth();
  const { active, info } = useActiveLanguage();
  const { t } = useI18n();
  const count = useQuery({ queryKey: wordsKey(user!.id, active, "", 0, "count"), queryFn: () => api.words({ language: active, limit: 1 }) });
  const name = info(active)?.native ?? active;
  return (
    <div>
      <PageHeader title={t("home.welcome", { name: user?.display_name ?? "" })} description={t("home.studying", { language: name })} />

      <div className="mb-8 grid gap-4 sm:grid-cols-2">
        <Card>
          <p className="text-sm font-medium text-slate-600">{t("home.words", { language: name })}</p>
          {count.data ? <p className="mt-1 text-4xl font-semibold tracking-tight text-slate-900">{count.data.total}</p> : <Skeleton className="mt-2 h-10 w-20" />}
          {count.data?.total === 0 && (
            <div className="mt-3">
              <p className="mb-3 text-sm text-slate-600">{t("home.empty")}</p>
              <Link to="/vocabulary"><Button icon={<BookOpen aria-hidden className="size-4" />}>{t("home.addFirst")}</Button></Link>
            </div>
          )}
        </Card>
        <Card>
          <p className="text-sm font-medium text-slate-600">{t("home.languages")}</p>
          <p className="mt-1 text-4xl font-semibold tracking-tight text-slate-900">{user?.languages.length}</p>
          <p className="mt-3 text-sm text-slate-600">{t("home.switchHint")}</p>
        </Card>
      </div>

      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">{t("home.next")}</h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {actions.map(({ to, title, text, icon: Icon }) => (
          <Link key={to} to={to} className="group rounded-xl border border-slate-200 bg-surface p-4 shadow-xs transition hover:border-brand-200 hover:shadow-sm dark:hover:border-brand-700">
            <div className="mb-3 flex items-center justify-between">
              <span className="flex size-9 items-center justify-center rounded-lg bg-brand-50 text-brand-600 dark:bg-brand-900/50 dark:text-brand-200"><Icon aria-hidden className="size-4.5" /></span>
              <ArrowRight aria-hidden className="size-4 text-slate-500 transition group-hover:translate-x-0.5 group-hover:text-brand-600 dark:group-hover:text-brand-200" />
            </div>
            <p className="font-medium text-slate-900">{t(title)}</p>
            <p className="mt-0.5 text-sm text-slate-600">{t(text)}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
