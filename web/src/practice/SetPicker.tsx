import { useQuery } from "@tanstack/react-query";
import type { SetFilter } from "../api/client";
import { api } from "../api/client";
import { setsKey } from "../api/keys";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n/I18nProvider";

/** What the learner picked, as the value the API takes: nothing picked = every word, else a comma list ("general,3,7"). */
export const pickedToFilter = (picked: string[]): SetFilter =>
  picked.length === 0 ? "all" : [...picked].sort((a, b) => (a === "general" ? -1 : b === "general" ? 1 : Number(a) - Number(b))).join(",");

/** Several sets at once: one chip per set (and General), each on or off. With none on, every word is used. Hidden while the learner
 * has no sets of their own, because there is nothing to choose between. */
export function SetPicker({ language, picked, onChange }: { language: string; picked: string[]; onChange: (picked: string[]) => void }) {
  const { user } = useAuth();
  const { t } = useI18n();
  const sets = useQuery({ queryKey: setsKey(user!.id, language), queryFn: () => api.sets(language) });
  const items = sets.data?.items ?? [];
  if (items.length === 0) return null;
  const toggle = (key: string) => onChange(picked.includes(key) ? picked.filter((k) => k !== key) : [...picked, key]);
  const chip = (key: string, label: string, count: number) => {
    const on = picked.includes(key);
    return (
      <button key={key} type="button" aria-pressed={on} onClick={() => toggle(key)}
        className={`rounded-full border px-3 py-1 text-sm ${on ? "border-brand-600 bg-brand-600 text-white" : "border-slate-300 bg-surface text-slate-700 hover:bg-slate-100/70"}`}>
        {label}<span className="ml-1">({count})</span>
      </button>
    );
  };
  return (
    <div className="mb-4" role="group" aria-labelledby="practice-set-label">
      <p id="practice-set-label" className="mb-1 text-sm font-medium text-slate-700">{t("practice.set")}</p>
      <div className="flex flex-wrap gap-2">
        {chip("general", t("sets.general"), sets.data!.general_count)}
        {items.map((s) => chip(String(s.id), s.name, s.count))}
      </div>
      <p className="mt-1 text-xs text-slate-600">{t("practice.sets.hint")}</p>
    </div>
  );
}
