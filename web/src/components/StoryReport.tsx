import { CircleAlert, CircleCheck } from "lucide-react";
import type { ReactNode } from "react";
import { useI18n } from "../i18n/I18nProvider";

/** The quality report the API made for a story (docs/WEB-APP-DESIGN.md section 8). Shown as plain sentences, because a
 * learner needs to know what it means, not what the fields are called. */
export interface Report {
  status?: string;
  language?: { requested?: string; ok?: boolean | null; verdict?: string };
  structure?: { ok?: boolean; leaked_plan?: boolean; units?: number };
  vocabulary?: { mode?: string; ok?: boolean | null; outside?: string[] | null; outside_count?: number; limit?: number | null };
  read_seconds?: number;
}

function Row({ ok, children }: { ok: boolean | null | undefined; children: ReactNode }) {
  const Icon = ok === false ? CircleAlert : CircleCheck;
  const tone = ok === false ? "text-red-700 dark:text-red-400" : ok ? "text-emerald-700 dark:text-emerald-400" : "text-slate-500";
  return (
    <li className="flex items-start gap-2">
      <Icon aria-hidden className={`mt-0.5 size-4 shrink-0 ${tone}`} />
      <span>{children}</span>
    </li>
  );
}

export function StoryReport({ report, languageName }: { report: Report; languageName: string }) {
  const { t, tc } = useI18n();
  const v = report.vocabulary ?? {};
  const outside = v.outside ?? [];
  return (
    <section aria-label={t("report.aria")} className="rounded-lg border border-slate-200 bg-slate-50/60 p-3 text-sm dark:bg-slate-100/40">
      <h3 className="font-medium text-slate-900">{report.status === "pass" ? t("common.looksGood") : t("common.needsLook")}</h3>
      <ul className="mt-2 space-y-1.5 text-slate-700">
        <Row ok={report.language?.ok}>
          {report.language?.ok === false ? t("report.notLanguage", { language: languageName }) : report.language?.ok ? t("report.written", { language: languageName }) : t("report.notChecked")}
        </Row>
        <Row ok={report.structure?.ok}>
          {report.structure?.ok ? t("report.shapeOk") : report.structure?.leaked_plan ? t("report.leaked") : t("report.shapeBad")}
        </Row>
        {v.mode === "unavailable" ? (
          <Row ok={null}>{t("report.vocabUnavailable")}</Row>
        ) : v.mode === "informational" ? (
          <Row ok={null}>
            {outside.length === 0 ? t("report.allFromList") : t("report.outsideInfo", { words: outside.join(", ") })}
          </Row>
        ) : (
          <Row ok={v.ok}>
            {outside.length === 0 ? t("report.allFromList") : tc("report.outside", v.outside_count ?? outside.length, { words: outside.join(", ") })}
          </Row>
        )}
      </ul>
      {report.read_seconds ? <p className="mt-2 text-xs text-slate-600">{t("report.readSeconds", { seconds: report.read_seconds })}</p> : null}
    </section>
  );
}
