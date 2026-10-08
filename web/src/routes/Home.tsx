import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BookOpen, Layers, Library, MessageCircle, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { wordsKey } from "../api/keys";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { useAuth } from "../auth/AuthContext";
import { Badge, Button, Card, PageHeader, Skeleton } from "../components/ui";

const actions = [
  { to: "/vocabulary", title: "Vocabulary", text: "Add, edit and upload your words.", icon: BookOpen, ready: true },
  { to: "/chat", title: "Chat", text: "Talk to the tutor in plain language.", icon: MessageCircle, ready: false },
  { to: "/studio", title: "Story Studio", text: "Generate a story from your words.", icon: Sparkles, ready: false },
  { to: "/practice", title: "Practice", text: "Flashcards and fill-in-the-blank.", icon: Layers, ready: false },
  { to: "/library", title: "Library", text: "Reread the stories you saved.", icon: Library, ready: false },
] as const;

export default function Home() {
  const { user } = useAuth();
  const { active, info } = useActiveLanguage();
  const count = useQuery({ queryKey: wordsKey(user!.id, active, "", 0, "count"), queryFn: () => api.words({ language: active, limit: 1 }) });
  const name = info(active)?.name ?? active;
  return (
    <div>
      <PageHeader title={`Welcome, ${user?.display_name}`} description={`You're studying ${name}.`} />

      <div className="mb-8 grid gap-4 sm:grid-cols-2">
        <Card>
          <p className="text-sm font-medium text-slate-600">{name} words</p>
          {count.data ? <p className="mt-1 text-4xl font-semibold tracking-tight text-slate-900">{count.data.total}</p> : <Skeleton className="mt-2 h-10 w-20" />}
          {count.data?.total === 0 && (
            <div className="mt-3">
              <p className="mb-3 text-sm text-slate-600">Nothing here yet. A few words are enough to start.</p>
              <Link to="/vocabulary"><Button icon={<BookOpen aria-hidden className="size-4" />}>Add your first words</Button></Link>
            </div>
          )}
        </Card>
        <Card>
          <p className="text-sm font-medium text-slate-600">Languages</p>
          <p className="mt-1 text-4xl font-semibold tracking-tight text-slate-900">{user?.languages.length}</p>
          <p className="mt-3 text-sm text-slate-600">Switch language from the menu at the top.</p>
        </Card>
      </div>

      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Where to next</h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {actions.map(({ to, title, text, icon: Icon, ready }) => (
          <Link key={to} to={to} className="group rounded-xl border border-slate-200 bg-surface p-4 shadow-xs transition hover:border-brand-200 hover:shadow-sm dark:hover:border-brand-700">
            <div className="mb-3 flex items-center justify-between">
              <span className="flex size-9 items-center justify-center rounded-lg bg-brand-50 text-brand-600 dark:bg-brand-900/50 dark:text-brand-200"><Icon aria-hidden className="size-4.5" /></span>
              {ready ? <ArrowRight aria-hidden className="size-4 text-slate-500 transition group-hover:translate-x-0.5 group-hover:text-brand-600 dark:group-hover:text-brand-200" /> : <Badge tone="accent">Soon</Badge>}
            </div>
            <p className="font-medium text-slate-900">{title}</p>
            <p className="mt-0.5 text-sm text-slate-600">{text}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
