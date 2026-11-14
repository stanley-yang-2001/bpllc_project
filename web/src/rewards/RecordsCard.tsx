import { Medal } from "lucide-react";
import type { Records } from "../api/types";
import { formatMs } from "../practice/session";
import { useI18n } from "../i18n/I18nProvider";
import { Card } from "../components/ui";
import { recordValue, RECORD_KINDS, type RecordKind } from "./records";

export const recordLabel = (kind: RecordKind) => ({ best_day: "rewards.records.bestDay", longest_run: "rewards.records.run", fastest_ms: "rewards.records.fastest", best_week_learned: "rewards.records.bestWeek" } as const)[kind];

/** The learner's own bests. Only compared with their own past. */
export function RecordsCard({ records }: { records: Records }) {
  const { t } = useI18n();
  const shown = RECORD_KINDS.map((k) => [k, recordValue(records, k)] as const).filter(([, v]) => v !== null);
  return (
    <Card className="mb-8">
      <section data-testid="records-card" aria-label={t("rewards.records.title")}>
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-500"><Medal aria-hidden className="size-4" />{t("rewards.records.title")}</h2>
        <p className="mt-1 text-sm text-slate-600">{shown.length ? t("rewards.records.note") : t("rewards.records.none")}</p>
        {shown.length > 0 && (
          <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {shown.map(([k, v]) => (
              <div key={k}>
                <dt className="text-sm text-slate-600">{t(recordLabel(k))}</dt>
                <dd className="text-xl font-semibold text-slate-900">{k === "fastest_ms" ? formatMs(v!) : v}</dd>
              </div>
            ))}
          </dl>
        )}
      </section>
    </Card>
  );
}
