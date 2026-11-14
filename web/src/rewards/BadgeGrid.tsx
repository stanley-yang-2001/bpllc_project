import { Award, Check } from "lucide-react";
import type { Badge } from "../api/types";
import { useI18n } from "../i18n/I18nProvider";
import { badgeText } from "./badgeText";

/** Every badge: earned ones marked with a tick and a word (not colour alone), the others with how far along and what to do. */
export function BadgeGrid({ badges }: { badges: Badge[] }) {
  const { t } = useI18n();
  return (
    <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {badges.map((b) => {
        const { name, how } = badgeText(b.id, b.target, t);
        return (
          <li key={b.id} data-testid={`badge-${b.id}`} data-earned={b.earned}
            className={`rounded-xl border p-4 ${b.earned ? "border-emerald-300 bg-emerald-50 dark:border-emerald-700 dark:bg-emerald-950/40" : "border-slate-200 bg-surface"}`}>
            <div className="flex items-start gap-3">
              <span aria-hidden className={`flex size-9 shrink-0 items-center justify-center rounded-full ${b.earned ? "bg-emerald-600 text-white" : "bg-slate-100 text-slate-500"}`}>
                {b.earned ? <Check className="size-5" /> : <Award className="size-5" />}
              </span>
              <div className="min-w-0">
                <p className="font-medium text-slate-900">{name}</p>
                <p className="text-sm text-slate-600">{how}</p>
                {b.earned
                  ? <p className="mt-1 text-xs font-medium text-emerald-800 dark:text-emerald-300">{t("rewards.badge.earned")}</p>
                  : (
                    <div className="mt-2">
                      <div role="progressbar" aria-label={name} aria-valuemin={0} aria-valuemax={b.target} aria-valuenow={b.have} className="h-1.5 overflow-hidden rounded-full bg-slate-200">
                        <div className="h-full rounded-full bg-brand-600" style={{ width: `${Math.round((b.have / b.target) * 100)}%` }} />
                      </div>
                      <p className="mt-1 text-xs text-slate-600">{t("rewards.badge.progress", { have: b.have, target: b.target })}</p>
                    </div>
                  )}
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
