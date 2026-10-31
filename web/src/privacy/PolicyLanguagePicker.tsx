import { useI18n } from "../i18n/I18nProvider";

/** Chooses which approved copy of the policy to read. Not shown when only one copy is offered. */
export function PolicyLanguagePicker({ offered, value, nameOf, onPick }: { offered: string[]; value: string; nameOf: (code: string) => string; onPick: (code: string) => void }) {
  const { t } = useI18n();
  if (offered.length < 2) return null;
  return (
    <div className="mb-6 flex items-center gap-2 text-sm text-slate-700">
      <label htmlFor="policy-lang">{t("privacy.picker")}</label>
      <select id="policy-lang" className="rounded-lg border border-slate-300 bg-surface px-2.5 py-1.5 text-sm shadow-xs" value={value} onChange={(e) => onPick(e.target.value)}>
        {offered.map((code) => <option key={code} value={code} lang={code}>{nameOf(code)}</option>)}
      </select>
    </div>
  );
}
