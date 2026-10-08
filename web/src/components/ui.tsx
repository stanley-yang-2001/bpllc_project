import { CircleAlert, CircleCheck, Info, LoaderCircle } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

/* Shared building blocks. Keep every colour, radius and shadow here so pages stay consistent. */

export const inputCls =
  "block w-full rounded-lg border border-slate-300 bg-surface px-3 py-2 text-sm text-slate-900 shadow-xs " +
  "placeholder:text-slate-500 transition focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30 " +
  "disabled:bg-slate-100 disabled:text-slate-500";

type Variant = "primary" | "secondary" | "danger" | "ghost";
const variants: Record<Variant, string> = {
  primary: "bg-brand-600 text-white shadow-xs hover:bg-brand-700 active:bg-brand-800 disabled:opacity-60",
  secondary: "border border-slate-300 bg-surface text-slate-700 shadow-xs hover:bg-slate-100/70 disabled:opacity-50",
  danger: "bg-red-600 text-white shadow-xs hover:bg-red-700 disabled:bg-slate-100 disabled:text-slate-400 disabled:shadow-none",
  ghost: "text-slate-600 hover:bg-slate-100 disabled:opacity-50",
};

export function Button({
  variant = "primary",
  loading = false,
  icon,
  className = "",
  children,
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean; icon?: ReactNode }) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition disabled:cursor-not-allowed ${variants[variant]} ${className}`}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? <LoaderCircle aria-hidden className="size-4 animate-spin" /> : icon}
      {children}
    </button>
  );
}

export const Card = ({ children, className = "" }: { children: ReactNode; className?: string }) => (
  <div className={`rounded-xl border border-slate-200 bg-surface p-5 shadow-xs ${className}`}>{children}</div>
);

export function PageHeader({ title, description, actions }: { title: ReactNode; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
        {description && <p className="mt-1 text-sm text-slate-600">{description}</p>}
      </div>
      {actions}
    </div>
  );
}

export const ErrorText = ({ children }: { children?: ReactNode }) =>
  children ? (
    <p role="alert" className="mt-1.5 flex items-start gap-1.5 text-sm text-red-700 dark:text-red-400">
      <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
      <span>{children}</span>
    </p>
  ) : null;

export const Spinner = ({ label = "Loading…" }: { label?: string }) => (
  <p role="status" className="flex items-center justify-center gap-2 py-10 text-sm text-slate-500">
    <LoaderCircle aria-hidden className="size-4 animate-spin" />
    {label}
  </p>
);

export const Skeleton = ({ className = "" }: { className?: string }) => (
  <div aria-hidden className={`animate-pulse rounded-md bg-slate-200/70 ${className}`} />
);

type Tone = "neutral" | "brand" | "accent" | "good" | "bad";
const tones: Record<Tone, string> = {
  neutral: "bg-slate-100 text-slate-700",
  brand: "bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-200 dark:bg-brand-900/50 dark:text-brand-200 dark:ring-brand-800",
  accent: "bg-accent-100 text-accent-800 dark:bg-accent-800/40 dark:text-accent-100",
  good: "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-300 dark:ring-emerald-900",
  bad: "bg-red-50 text-red-700 ring-1 ring-inset ring-red-200 dark:bg-red-950/50 dark:text-red-300 dark:ring-red-900",
};
export const Badge = ({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) => (
  <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>{children}</span>
);

export function EmptyState({ icon, title, children, action }: { icon: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-4 py-12 text-center">
      <div className="mb-3 flex size-12 items-center justify-center rounded-full bg-brand-50 text-brand-600 dark:bg-brand-900/50 dark:text-brand-200">{icon}</div>
      <h2 className="text-base font-semibold text-slate-900">{title}</h2>
      {children && <p className="mt-1 max-w-sm text-sm text-slate-600">{children}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Notice({ tone = "info", children, ...rest }: { tone?: "info" | "success" | "warning"; children: ReactNode } & React.HTMLAttributes<HTMLDivElement>) {
  const styles = {
    info: ["border-brand-200 bg-brand-50 text-brand-900 dark:border-brand-800 dark:bg-brand-900/40 dark:text-brand-100", <Info key="i" aria-hidden className="size-4" />],
    success: ["border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100", <CircleCheck key="c" aria-hidden className="size-4" />],
    warning: ["border-accent-100 bg-accent-50 text-accent-800 dark:border-accent-800/60 dark:bg-accent-800/20 dark:text-accent-100", <CircleAlert key="a" aria-hidden className="size-4" />],
  }[tone];
  return (
    <div className={`flex gap-2 rounded-lg border p-3 text-sm ${styles[0]}`} {...rest}>
      <span className="mt-0.5 shrink-0">{styles[1]}</span>
      <div className="min-w-0">{children}</div>
    </div>
  );
}
