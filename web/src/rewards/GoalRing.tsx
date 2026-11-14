import { Check } from "lucide-react";

/** A ring that fills as today's answers approach the goal. Not colour alone: it shows a tick when reached, and says the numbers in text. */
export function GoalRing({ done, target, label, valueText }: { done: number; target: number; label: string; valueText: string }) {
  const share = Math.min(1, target > 0 ? done / target : 0);
  const r = 30, c = 2 * Math.PI * r;
  const reached = done >= target;
  return (
    <div role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={target} aria-valuenow={Math.min(done, target)} aria-valuetext={valueText}
      className="relative size-20 shrink-0">
      <svg viewBox="0 0 72 72" className="size-20 -rotate-90" aria-hidden>
        <circle cx="36" cy="36" r={r} fill="none" strokeWidth="7" className="stroke-slate-200" />
        <circle cx="36" cy="36" r={r} fill="none" strokeWidth="7" strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - share)}
          className={`${reached ? "stroke-emerald-600 dark:stroke-emerald-400" : "stroke-brand-600"} motion-safe:transition-[stroke-dashoffset] motion-safe:duration-700`} />
      </svg>
      <div aria-hidden className="absolute inset-0 flex items-center justify-center text-sm font-semibold text-slate-900">
        {reached ? <Check className="size-6 text-emerald-700 dark:text-emerald-300" /> : <>{done}<span className="font-normal text-slate-500">/{target}</span></>}
      </div>
    </div>
  );
}
