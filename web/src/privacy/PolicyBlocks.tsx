import { Fragment, type ReactNode } from "react";
import { inline } from "./inline";
import type { Block } from "./types";

const Th = ({ children }: { children: ReactNode }) => <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">{children}</th>;

/** One block kind, one small renderer; a new kind of block is a new entry here and a new member of `Block`. */
const render: { [K in Block["type"]]: (b: Extract<Block, { type: K }>, contact: string | null | undefined) => ReactNode } = {
  p: (b, contact) => <p>{inline(!contact && b.text_without_contact ? b.text_without_contact : b.text, contact)}</p>,
  list: (b, contact) => <ul className="list-disc space-y-1.5 pl-5">{b.items.map((it, j) => <li key={j}>{inline(it, contact)}</li>)}</ul>,
  table: (b, contact) => (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
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
  ),
};

export function PolicyBlocks({ blocks, contact }: { blocks: Block[]; contact?: string | null }) {
  return <>{blocks.map((b, i) => <Fragment key={i}>{(render[b.type] as (b: Block, c: string | null | undefined) => ReactNode)(b, contact)}</Fragment>)}</>;
}
