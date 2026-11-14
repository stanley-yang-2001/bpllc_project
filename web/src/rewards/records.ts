import type { Records } from "../api/types";

export type RecordKind = "best_day" | "longest_run" | "fastest_ms" | "best_week_learned";
export const RECORD_KINDS: RecordKind[] = ["best_day", "longest_run", "fastest_ms", "best_week_learned"];
export type Seen = Partial<Record<RecordKind, number>>;

/** The number behind each record, or null when there is none yet. */
export function recordValue(r: Records, kind: RecordKind): number | null {
  const v = kind === "best_day" ? r.best_day?.value : kind === "fastest_ms" ? r.fastest_ms : r[kind];
  return v ? v : null;
}

/** Records that beat what this browser last saw. A record with no earlier value to beat (the very first one) is not news, and a
 * lower time is better for "fastest". */
export function beaten(seen: Seen, r: Records): RecordKind[] {
  return RECORD_KINDS.filter((k) => {
    const before = seen[k], now = recordValue(r, k);
    if (!before || now === null) return false;
    return k === "fastest_ms" ? now < before : now > before;
  });
}

/** What to remember after looking: the current numbers (the best of what was seen and what is now). */
export function remember(seen: Seen, r: Records): Seen {
  const out: Seen = { ...seen };
  for (const k of RECORD_KINDS) {
    const now = recordValue(r, k);
    if (now === null) continue;
    const before = out[k];
    out[k] = !before ? now : k === "fastest_ms" ? Math.min(before, now) : Math.max(before, now);
  }
  return out;
}
