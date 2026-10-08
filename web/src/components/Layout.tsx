import { BookOpen, House, Languages, Layers, Library, LogOut, MessageCircle, Settings, Sparkles } from "lucide-react";
import { NavLink, Link, Outlet } from "react-router-dom";
import { ThemeToggle } from "./ThemeToggle";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { useAuth } from "../auth/AuthContext";

const links = [
  ["/", "Home", House],
  ["/chat", "Chat", MessageCircle],
  ["/vocabulary", "Vocabulary", BookOpen],
  ["/studio", "Studio", Sparkles],
  ["/library", "Library", Library],
  ["/practice", "Practice", Layers],
  ["/settings", "Settings", Settings],
] as const;

const initials = (name: string) =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]!.toUpperCase()).join("") || "?";

export function Layout() {
  const { user, logout } = useAuth();
  const { active, setActive, studying } = useActiveLanguage();
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-surface/85 backdrop-blur">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-3 px-4">
          <Link to="/" className="flex h-14 items-center gap-2 font-semibold tracking-tight text-slate-900">
            <span className="flex size-8 items-center justify-center rounded-lg bg-brand-600 text-white shadow-xs">
              <Languages aria-hidden className="size-4.5" />
            </span>
            Language Tutor
          </Link>

          {/* One nav, always its own row (scrolls sideways on phones). A single row for everything only fit by luck. */}
          <nav aria-label="Main" className="order-last -mx-4 flex w-[calc(100%+2rem)] gap-1 overflow-x-auto px-4 pb-2">
            {links.map(([to, label, Icon]) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  `flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm transition ${
                    isActive ? "bg-brand-50 font-medium text-brand-700 dark:bg-brand-900/50 dark:text-brand-200" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                  }`
                }
              >
                <Icon aria-hidden className="hidden size-4 sm:block" />
                {label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-2">
            <label className="flex items-center gap-1.5 rounded-lg border border-slate-300 bg-surface py-1 pl-2.5 pr-1 text-sm shadow-xs">
              <span className="hidden text-slate-500 sm:inline">Studying</span>
              <select
                aria-label="Active language"
                value={active}
                onChange={(e) => setActive(e.target.value)}
                className="rounded-md bg-transparent py-0.5 pr-1 font-medium text-slate-900 focus:outline-none"
              >
                {studying.map((l) => (
                  <option key={l.code} value={l.code}>{l.name}</option>
                ))}
              </select>
            </label>
            <div className="hidden items-center gap-2 pl-1 sm:flex">
              <span aria-hidden className="flex size-8 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700 dark:bg-brand-800 dark:text-brand-100">
                {initials(user?.display_name ?? "")}
              </span>
              <span className="max-w-32 truncate text-sm text-slate-700">{user?.display_name}</span>
            </div>
            <ThemeToggle />
            <button
              aria-label="Log out"
              title="Log out"
              onClick={() => void logout()}
              className="flex size-9 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
            >
              <LogOut aria-hidden className="size-4.5" />
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-8">
        <Outlet />
      </main>
      <footer className="mx-auto max-w-5xl px-4 pb-8 text-xs text-slate-500">
        <Link to="/privacy" className="underline-offset-2 hover:text-slate-900 hover:underline">Privacy Policy</Link>
      </footer>
    </div>
  );
}
