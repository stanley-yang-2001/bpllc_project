/** The order of a flashcard session, with no React and no clock of its own (the caller passes `now`, in milliseconds).
 *
 * The server decides when a word is due again (srs.py); this only decides what to show next in one sitting. A word that was
 * answered and comes back within 20 minutes (a learning step: 1 or 10 minutes) stays in the session: it is shown again once its
 * time has come, and when nothing else is left it is shown early rather than making the learner wait. Words due later leave. */
import type { Flashcard, Grade, ReviewResult } from "../api/types";

export const LEARN_AHEAD_SECONDS = 20 * 60;

export interface Entry { id: number; word: string; grade: Grade; think_ms: number; rate_ms: number }
interface Pending { card: Flashcard; showAt: number }
export interface Session { queue: Flashcard[]; pending: Pending[]; log: Entry[] }

export const startSession = (cards: Flashcard[]): Session => ({ queue: [...cards], pending: [], log: [] });

/** Cards not yet answered for good, counting the ones waiting for their step (the card on screen is counted by the caller). */
export const remaining = (s: Session) => s.queue.length + s.pending.length;

/** Takes the next card: one whose short step is over, else the next new card, else (learn-ahead) the one coming back soonest. */
export function take(s: Session, now: number): { session: Session; card: Flashcard | null } {
  const ripe = s.pending.filter((p) => p.showAt <= now).sort((a, b) => a.showAt - b.showAt)[0];
  if (ripe) return { session: { ...s, pending: s.pending.filter((p) => p !== ripe) }, card: ripe.card };
  if (s.queue.length > 0) return { session: { ...s, queue: s.queue.slice(1) }, card: s.queue[0] };
  const soonest = [...s.pending].sort((a, b) => a.showAt - b.showAt)[0];
  if (soonest) return { session: { ...s, pending: s.pending.filter((p) => p !== soonest) }, card: soonest.card };
  return { session: s, card: null };
}

/** Records an answer. The card goes back into the session when the server says it comes back within the look-ahead. */
export function answered(s: Session, card: Flashcard, grade: Grade, result: ReviewResult | null, now: number, think_ms: number, rate_ms: number): Session {
  const log = [...s.log, { id: card.id, word: card.word, grade, think_ms, rate_ms }];
  if (!result) return { ...s, log };                                  // not saved: do not keep asking about it
  const back = result.delay_seconds <= LEARN_AHEAD_SECONDS && (result.status === "learning" || result.status === "relearning");
  if (!back) return { ...s, log };
  const next: Flashcard = { ...card, status: result.status, ease: result.ease, interval_days: result.interval_days, lapses: result.lapses, preview: result.preview };
  return { ...s, log, pending: [...s.pending, { card: next, showAt: now + result.delay_seconds * 1000 }] };
}

export interface Summary {
  answers: number;
  words: number;
  counts: Record<Grade, number>;
  /** Share of answers that were not "again" (0 to 1). */
  accuracy: number;
  avgThinkMs: number;
  /** The words that took longest to answer (first answer of each), slowest first. */
  slowest: { id: number; word: string; ms: number }[];
  /** Words answered "again" at least once, for "practise the ones I missed". */
  missed: { id: number; word: string }[];
}

export function summarize(log: Entry[]): Summary {
  const counts: Record<Grade, number> = { 1: 0, 2: 0, 3: 0, 4: 0 };
  const first = new Map<number, Entry>();
  const missed = new Map<number, string>();
  for (const e of log) {
    counts[e.grade] += 1;
    if (!first.has(e.id)) first.set(e.id, e);
    if (e.grade === 1) missed.set(e.id, e.word);
  }
  const answers = log.length;
  const avgThinkMs = answers ? Math.round(log.reduce((n, e) => n + e.think_ms, 0) / answers) : 0;
  const slowest = [...first.values()].sort((a, b) => b.think_ms - a.think_ms).slice(0, 3).filter((e) => e.think_ms > 0).map((e) => ({ id: e.id, word: e.word, ms: e.think_ms }));
  return { answers, words: first.size, counts, accuracy: answers ? (answers - counts[1]) / answers : 0, avgThinkMs, slowest, missed: [...missed].map(([id, word]) => ({ id, word })) };
}

/** Seconds as the short text on a grade button: "<1m", "10m", "2h", "1d", "3w", "4mo". `unit` gives each unit's text (translated). */
export function delayParts(seconds: number): { n: number; unit: "lt1m" | "m" | "h" | "d" | "w" | "mo" } {
  const s = Math.max(0, seconds);
  if (s < 60) return { n: 0, unit: "lt1m" };
  if (s < 3600) return { n: Math.round(s / 60), unit: "m" };
  if (s < 86400) return { n: Math.round(s / 3600), unit: "h" };
  const d = s / 86400;
  if (d < 14) return { n: Math.round(d), unit: "d" };
  if (d < 60) return { n: Math.round(d / 7), unit: "w" };
  return { n: Math.round(d / 30), unit: "mo" };
}

/** A time taken, as "3.2s" (under a minute) or "1m 05s". */
export function formatMs(ms: number): string {
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  const total = Math.round(ms / 1000);
  return `${Math.floor(total / 60)}m ${String(total % 60).padStart(2, "0")}s`;
}
