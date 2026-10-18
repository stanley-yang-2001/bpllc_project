import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Languages } from "lucide-react";
import { Fragment, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ThemeToggle } from "../components/ThemeToggle";
import { Skeleton } from "../components/ui";
import { useI18n } from "../i18n/I18nProvider";

/* The policy is data, not markup (docs/WEB-APP-DESIGN.md 3I): the API serves one complete copy per language and this
   page only builds elements from it. Text is never injected as HTML. Inline formatting is a small safe subset:
   **bold** and a {contact} placeholder for the operator's address. If behaviour changes, change the English copy in
   api/app/policy/en.json and bump POLICY_VERSION in api/app/policy/__init__.py. */

type Block =
  | { type: "p"; text: string; text_without_contact?: string }
  | { type: "list"; items: string[] }
  | { type: "table"; caption: string; head: string[]; rows: string[][] };
interface Doc {
  title: string;
  summary: { title: string; items: string[] };
  sections: { id: string; title: string; blocks: Block[] }[];
  governing: string;
}

const linkCls = "text-brand-600 underline dark:text-brand-200";

/** `**bold**` and `{contact}` to elements. Everything else is plain text, which React escapes. */
function inline(text: string, contact: string | null | undefined): ReactNode {
  return text.split(/(\*\*[^*]+\*\*|\{contact\})/g).map((part, i) => {
    if (part === "{contact}") return contact ? <a key={i} className={linkCls} href={`mailto:${contact}`}>{contact}</a> : null;
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={i}>{part.slice(2, -2)}</strong>;
    return <Fragment key={i}>{part}</Fragment>;
  });
}

const Th = ({ children }: { children: ReactNode }) => <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">{children}</th>;

function Blocks({ blocks, contact }: { blocks: Block[]; contact?: string | null }) {
  return (
    <>
      {blocks.map((b, i) => {
        if (b.type === "p") return <p key={i}>{inline(!contact && b.text_without_contact ? b.text_without_contact : b.text, contact)}</p>;
        if (b.type === "list") return <ul key={i} className="list-disc space-y-1.5 pl-5">{b.items.map((it, j) => <li key={j}>{inline(it, contact)}</li>)}</ul>;
        return (
          <div key={i} className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="w-full text-sm">
              <caption className="sr-only">{b.caption}</caption>
              <thead className="border-b border-slate-200 bg-slate-100/60"><tr>{b.head.map((h, j) => <Th key={j}>{h}</Th>)}</tr></thead>
              <tbody className="divide-y divide-slate-100">
                {b.rows.map((r, j) => (
                  <tr key={j}>{r.map((cell, k) => <td key={k} className={`px-3 py-2.5 align-top ${k === 0 ? "font-medium text-slate-900" : ""}`}>{inline(cell, contact)}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
    </>
  );
}

export default function Privacy() {
  const { user } = useAuth();
  const { t, locale } = useI18n();
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: Infinity });
  const languages = useQuery({ queryKey: ["languages"], queryFn: api.languages, staleTime: Infinity });
  const offered = meta.data?.policy_languages ?? ["en"];
  const [picked, setPicked] = useState<string | null>(null);
  // the learner's interface language unless they chose another with the picker
  const wanted = picked ?? locale;
  const policy = useQuery({ queryKey: ["policy", wanted], queryFn: () => api.policy(wanted), staleTime: Infinity, enabled: meta.isSuccess || meta.isError });
  const contact = meta.data?.privacy_contact;
  const doc = policy.data?.doc as unknown as Doc | undefined;
  const name = (code: string) => languages.data?.find((l) => l.code === code)?.native ?? code;

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-surface">
        <div className="mx-auto flex h-14 max-w-3xl items-center justify-between px-4">
          <Link to={user ? "/settings" : "/login"} className="flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-900">
            <ArrowLeft aria-hidden className="size-4" />
            {user ? t("privacy.backApp") : t("privacy.backSignIn")}
          </Link>
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-2 text-sm font-semibold tracking-tight text-slate-900">
              <span className="flex size-7 items-center justify-center rounded-md bg-brand-600 text-white"><Languages aria-hidden className="size-4" /></span>
              Language Tutor
            </span>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-10">
        {offered.length > 1 && (
          <div className="mb-6 flex items-center gap-2 text-sm text-slate-700">
            <label htmlFor="policy-lang">{t("privacy.picker")}</label>
            <select id="policy-lang" className="rounded-lg border border-slate-300 bg-surface px-2.5 py-1.5 text-sm shadow-xs" value={policy.data?.language ?? wanted} onChange={(e) => setPicked(e.target.value)}>
              {offered.map((code) => <option key={code} value={code} lang={code}>{name(code)}</option>)}
            </select>
          </div>
        )}
        {policy.data?.fallback && <p role="status" className="mb-6 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-900/30 dark:text-amber-100">{t("privacy.fallback")}</p>}

        {!doc ? (
          <div role="status" aria-label={t("privacy.loading")} className="space-y-3"><Skeleton className="h-9 w-2/3" /><Skeleton className="h-24 w-full" /></div>
        ) : (
          <div lang={policy.data!.language}>
            <h1 className="text-3xl font-semibold tracking-tight text-slate-900">{doc.title}</h1>
            <p className="mt-2 text-sm text-slate-500">{t("privacy.version", { version: policy.data!.version })} {t("privacy.plain")}</p>

            <div className="mt-6 rounded-xl border border-brand-200 bg-brand-50 p-4 text-[15px] text-brand-900 dark:border-brand-800 dark:bg-brand-900/40 dark:text-brand-100">
              <p className="font-semibold">{doc.summary.title}</p>
              <ul className="mt-2 list-disc space-y-1 pl-5">{doc.summary.items.map((it, i) => <li key={i}>{inline(it, contact)}</li>)}</ul>
            </div>

            {doc.sections.map((s) => (
              <section key={s.id} aria-labelledby={s.id} className="mt-10">
                <h2 id={s.id} className="text-lg font-semibold tracking-tight text-slate-900">{s.title}</h2>
                <div className="mt-3 space-y-3 text-[15px] leading-relaxed text-slate-700"><Blocks blocks={s.blocks} contact={contact} /></div>
              </section>
            ))}
            <p className="mt-10 border-t border-slate-200 pt-4 text-sm text-slate-600">{doc.governing}</p>
          </div>
        )}
      </main>
    </div>
  );
}
