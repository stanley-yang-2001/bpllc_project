import { type Health } from "../api/client";
import { useI18n } from "../i18n/I18nProvider";

export function ServiceRow({ label, check }: { label: string; check: Health["postgres"] }) {
  const { t } = useI18n();
  const state = check.ok === true ? t("settings.services.ok") : check.ok === false ? `${t("settings.services.problem")}${check.detail ? ` (${check.detail})` : ""}`
    : check.status === "stub" ? t("settings.services.stub") : t("settings.services.unchecked");
  const dot = check.ok === true ? "bg-emerald-500" : check.ok === false ? "bg-red-500" : "bg-slate-300";
  return (
    <li className="flex items-center justify-between border-b border-slate-100 py-3 last:border-0">
      <span className="flex items-center gap-2.5 text-sm text-slate-800">
        <span aria-hidden className={`size-2.5 rounded-full ${dot}`} />
        {label}
      </span>
      <span className="text-sm text-slate-600">{state}</span>
    </li>
  );
}
