import { CircleAlert, CircleCheck } from "lucide-react";
import type { ReactNode } from "react";

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
  const v = report.vocabulary ?? {};
  const outside = v.outside ?? [];
  return (
    <section aria-label="Quality report" className="rounded-lg border border-slate-200 bg-slate-50/60 p-3 text-sm dark:bg-slate-100/40">
      <h3 className="font-medium text-slate-900">{report.status === "pass" ? "Looks good" : "Needs a look"}</h3>
      <ul className="mt-2 space-y-1.5 text-slate-700">
        <Row ok={report.language?.ok}>
          {report.language?.ok === false ? `This doesn't look like ${languageName}.` : report.language?.ok ? `Written in ${languageName}.` : "Language not checked."}
        </Row>
        <Row ok={report.structure?.ok}>
          {report.structure?.ok ? "Short and in the right shape." : report.structure?.leaked_plan ? "The writer's plan was left in the story." : "Not the right length or shape."}
        </Row>
        {v.mode === "unavailable" ? (
          <Row ok={null}>Your word list isn't checked for this language yet.</Row>
        ) : v.mode === "informational" ? (
          <Row ok={null}>
            {outside.length === 0 ? "Every word is from your list." : `Words outside your list (shown for information, not scored): ${outside.join(", ")}.`}
          </Row>
        ) : (
          <Row ok={v.ok}>
            {outside.length === 0 ? "Every word is from your list." : `${v.outside_count} word${v.outside_count === 1 ? "" : "s"} outside your list: ${outside.join(", ")}.`}
          </Row>
        )}
      </ul>
      {report.read_seconds ? <p className="mt-2 text-xs text-slate-600">About {report.read_seconds} seconds to read.</p> : null}
    </section>
  );
}
