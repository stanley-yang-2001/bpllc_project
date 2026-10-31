import { useI18n } from "../i18n/I18nProvider";
import { inline } from "./inline";
import { PolicyBlocks } from "./PolicyBlocks";
import type { PolicyDoc } from "./types";

/** The policy text: title, version line, the summary box, each section and the governing-law line. */
export function PolicyDocument({ doc, language, version, contact }: { doc: PolicyDoc; language: string; version: string; contact?: string | null }) {
  const { t } = useI18n();
  return (
    <div lang={language}>
      <h1 className="text-3xl font-semibold tracking-tight text-slate-900">{doc.title}</h1>
      <p className="mt-2 text-sm text-slate-500">{t("privacy.version", { version })} {t("privacy.plain")}</p>

      <div className="mt-6 rounded-xl border border-brand-200 bg-brand-50 p-4 text-[15px] text-brand-900 dark:border-brand-800 dark:bg-brand-900/40 dark:text-brand-100">
        <p className="font-semibold">{doc.summary.title}</p>
        <ul className="mt-2 list-disc space-y-1 pl-5">{doc.summary.items.map((it, i) => <li key={i}>{inline(it, contact)}</li>)}</ul>
      </div>

      {doc.sections.map((s) => (
        <section key={s.id} aria-labelledby={s.id} className="mt-10">
          <h2 id={s.id} className="text-lg font-semibold tracking-tight text-slate-900">{s.title}</h2>
          <div className="mt-3 space-y-3 text-[15px] leading-relaxed text-slate-700"><PolicyBlocks blocks={s.blocks} contact={contact} /></div>
        </section>
      ))}
      <p className="mt-10 border-t border-slate-200 pt-4 text-sm text-slate-600">{doc.governing}</p>
    </div>
  );
}
