import type { UploadResult } from "../api/client";
import { useI18n } from "../i18n/I18nProvider";
import { Notice } from "../components/ui";

/** What a CSV upload did: how many words were added, skipped as duplicates, or rejected (with the row and the reason). */
export function UploadNotice({ result }: { result: UploadResult }) {
  const { t } = useI18n();
  return (
    <Notice tone={result.invalid_count ? "warning" : "success"} role="status">
      <p>{t("vocab.upload.result", { added: result.added, duplicates: result.duplicates, invalid: result.invalid_count })}</p>
      {result.invalid.length > 0 && (
        <ul className="mt-1 list-disc pl-5 text-xs">
          {result.invalid.map((r) => <li key={r.row}>{t("vocab.upload.row", { row: r.row, reason: r.reason })}</li>)}
        </ul>
      )}
    </Notice>
  );
}
