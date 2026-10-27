import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { setsKey } from "../api/keys";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n/I18nProvider";

/** General is id 0 in a list of set ids (the same number the API and the tutor use). */
export const GENERAL_ID = 0;

/** `null` means every set is used (nothing is sent). Otherwise the ids the learner ticked, General being 0. */
export type SetChoice = number[] | null;

/** What to send: nothing when every set is ticked (the picker turns that back into null), else the ticked ids. */
export const setIdsToSend = (choice: SetChoice): number[] | undefined => choice ?? undefined;

/** The learner's sets as one list of tick boxes. General is always listed, and it is the only one when the learner has made none. */
export function SetPicker({ language, value, onChange, idPrefix }: { language: string; value: SetChoice; onChange: (v: SetChoice) => void; idPrefix: string }) {
  const { user } = useAuth();
  const { t } = useI18n();
  const sets = useQuery({ queryKey: setsKey(user!.id, language), queryFn: () => api.sets(language) });
  const options = [{ id: GENERAL_ID, name: t("sets.general"), count: sets.data?.general_count }, ...(sets.data?.items ?? []).map((s) => ({ id: s.id, name: s.name, count: s.count }))];
  if (options.length === 1) return null;             // only General: nothing to choose, and nothing to explain
  const allIds = options.map((o) => o.id);
  const ticked = value ?? allIds;
  const toggle = (id: number) => {
    const next = ticked.includes(id) ? ticked.filter((x) => x !== id) : [...ticked, id];
    onChange(next.length === allIds.length ? null : next);
  };
  return (
    <fieldset>
      <legend className="mb-1 text-sm font-medium text-slate-700">{t("sets.pickerLegend")}</legend>
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {options.map((o) => (
          <label key={o.id} htmlFor={`${idPrefix}-${o.id}`} className="inline-flex items-center gap-2 text-sm text-slate-800">
            <input id={`${idPrefix}-${o.id}`} type="checkbox" className="size-4 rounded accent-brand-600" checked={ticked.includes(o.id)} onChange={() => toggle(o.id)} />
            {o.name}{o.count !== undefined && <span className="text-xs text-slate-600">({o.count})</span>}
          </label>
        ))}
      </div>
      <p className={`mt-1 text-xs ${ticked.length === 0 ? "text-red-700" : "text-slate-600"}`}>{ticked.length === 0 ? t("sets.pickerNone") : t("sets.pickerHint")}</p>
    </fieldset>
  );
}

/** True when the learner unticked everything: sending would mean "no words at all", so the page blocks it. */
export const nothingTicked = (choice: SetChoice) => choice !== null && choice.length === 0;
