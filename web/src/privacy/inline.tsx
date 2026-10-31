import { Fragment, type ReactNode } from "react";

const linkCls = "text-brand-600 underline dark:text-brand-200";

/** `**bold**` and `{contact}` to elements. Everything else is plain text, which React escapes (the policy is never injected as HTML). */
export function inline(text: string, contact: string | null | undefined): ReactNode {
  return text.split(/(\*\*[^*]+\*\*|\{contact\})/g).map((part, i) => {
    if (part === "{contact}") return contact ? <a key={i} className={linkCls} href={`mailto:${contact}`}>{contact}</a> : null;
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={i}>{part.slice(2, -2)}</strong>;
    return <Fragment key={i}>{part}</Fragment>;
  });
}
