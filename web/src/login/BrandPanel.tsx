import { BookOpen, Languages, ShieldCheck, Sparkles } from "lucide-react";

const points = [
  [BookOpen, "A separate word list for every language you study"],
  [Sparkles, "Stories written from the words you already know"],
  [ShieldCheck, "We keep only your name and email, and your words stay private"],
] as const;

/** The left-hand panel shown on wide screens. */
export function BrandPanel() {
  return (
    <aside className="relative hidden flex-col justify-between overflow-hidden bg-gradient-to-br from-brand-700 via-brand-600 to-brand-900 p-12 text-white lg:flex">
      <div className="flex items-center gap-2 text-lg font-semibold tracking-tight">
        <span className="flex size-9 items-center justify-center rounded-lg bg-white/15"><Languages aria-hidden className="size-5" /></span>
        Language Tutor
      </div>
      <div>
        <p className="text-4xl font-semibold leading-tight tracking-tight">Learn with the words<br />you actually know.</p>
        <ul className="mt-8 space-y-4 text-brand-100">
          {points.map(([Icon, text]) => (
            <li key={text} className="flex items-start gap-3">
              <Icon aria-hidden className="mt-0.5 size-5 shrink-0 text-white" />
              <span>{text}</span>
            </li>
          ))}
        </ul>
      </div>
      <p className="text-sm text-brand-200">Runs on your own computer.</p>
      <div aria-hidden className="pointer-events-none absolute -right-24 -top-24 size-80 rounded-full bg-white/5" />
      <div aria-hidden className="pointer-events-none absolute -bottom-32 -left-16 size-96 rounded-full bg-white/5" />
    </aside>
  );
}
