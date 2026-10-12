import { CircleAlert, Wrench } from "lucide-react";
import type { ToolCall } from "../api/client";

/** What the tutor did behind the scenes for one reply: which tool, with what, and what came back. Collapsed by
 * default, because most learners only want the answer; a learner (or a developer) can open it to check. */
export function ToolTrace({ calls }: { calls: ToolCall[] }) {
  if (calls.length === 0) return null;
  return (
    <div className="mt-2 space-y-1.5">
      {calls.map((call, i) => (
        <details key={i} className="group rounded-lg border border-slate-200 bg-slate-50/60 text-xs text-slate-700 dark:bg-slate-100/40">
          <summary className="flex cursor-pointer list-none items-center gap-1.5 rounded-lg px-2.5 py-1.5 font-medium hover:bg-slate-100/70 focus-visible:outline-2 focus-visible:outline-brand-500">
            {call.failed ? <CircleAlert aria-hidden className="size-3.5 text-red-600 dark:text-red-400" /> : <Wrench aria-hidden className="size-3.5 text-slate-500" />}
            <span>{call.failed ? `${call.name} didn't work` : `Used ${call.name}`}</span>
          </summary>
          <dl className="space-y-1.5 border-t border-slate-200 px-2.5 py-2">
            <div>
              <dt className="font-medium text-slate-600">Sent</dt>
              <dd><code className="break-words">{JSON.stringify(call.args)}</code></dd>
            </div>
            <div>
              <dt className="font-medium text-slate-600">Returned</dt>
              <dd className="whitespace-pre-wrap break-words">{call.output || "(nothing)"}</dd>
            </div>
          </dl>
        </details>
      ))}
    </div>
  );
}
