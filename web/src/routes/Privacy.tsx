import { Skeleton } from "../components/ui";
import { useI18n } from "../i18n/I18nProvider";
import { PolicyDocument } from "../privacy/PolicyDocument";
import { PolicyLanguagePicker } from "../privacy/PolicyLanguagePicker";
import { PolicyTopBar } from "../privacy/PolicyTopBar";
import { usePolicy } from "../privacy/usePolicy";

/* The policy is data, not markup (docs/WEB-APP-DESIGN.md 3I): the API serves one complete copy per language and this
   page only builds elements from it (privacy/). Text is never injected as HTML. Inline formatting is a small safe subset:
   **bold** and a {contact} placeholder for the operator's address. If behaviour changes, change the English copy in
   api/app/policy/en.json and bump POLICY_VERSION in api/app/policy/__init__.py. */
export default function Privacy() {
  const { t } = useI18n();
  const p = usePolicy();
  return (
    <div className="min-h-screen">
      <PolicyTopBar />
      <main className="mx-auto max-w-3xl px-4 py-10">
        <PolicyLanguagePicker offered={p.offered} value={p.shown} nameOf={p.nameOf} onPick={p.setPicked} />
        {p.data?.fallback && <p role="status" className="mb-6 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-900/30 dark:text-amber-100">{t("privacy.fallback")}</p>}
        {!p.doc || !p.data ? (
          <div role="status" aria-label={t("privacy.loading")} className="space-y-3"><Skeleton className="h-9 w-2/3" /><Skeleton className="h-24 w-full" /></div>
        ) : (
          <PolicyDocument doc={p.doc} language={p.data.language} version={p.data.version} contact={p.contact} />
        )}
      </main>
    </div>
  );
}
