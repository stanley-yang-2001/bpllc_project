import { describe, expect, it } from "vitest";
import type { Flashcard, Grade, ReviewResult } from "../api/types";
import { answered, delayParts, formatMs, remaining, startSession, summarize, take } from "./session";

const card = (id: number, word = `w${id}`): Flashcard => ({ id, word, meaning: "m", status: "new", ease: 2.5, interval_days: 0, lapses: 0, reps: 0, leech: false, due_at: null, preview: { again: 60, hard: 90, good: 600, easy: 345600 } });
const result = (over: Partial<ReviewResult> = {}): ReviewResult => ({ word_id: 1, delay_seconds: 600, status: "learning", counted: true, correct: true, box: 1, ease: 2.5, interval_days: 0, lapses: 0, preview: { again: 60, hard: 900, good: 86400, easy: 345600 }, ...over });

describe("session order", () => {
  it("shows the cards in order, then nothing", () => {
    let s = startSession([card(1), card(2)]);
    const a = take(s, 0); s = a.session;
    const b = take(s, 0); s = b.session;
    expect([a.card?.id, b.card?.id, take(s, 0).card]).toEqual([1, 2, null]);
    expect(remaining(s)).toBe(0);
  });

  it("brings a word back after its step while other cards are waiting, and not before", () => {
    let s = startSession([card(1), card(2), card(3)]);
    const first = take(s, 0); s = first.session;
    s = answered(s, first.card!, 3, result({ delay_seconds: 600 }), 0, 1000, 500);       // 10 minutes
    expect(take(s, 60_000).card?.id).toBe(2);                                              // one minute later: the next new card
    const later = take(s, 600_000);
    expect(later.card?.id).toBe(1);                                                        // ten minutes later: it is due, so it comes first
    expect(later.card?.status).toBe("learning");
  });

  it("shows the soonest waiting word early when nothing else is left", () => {
    let s = startSession([card(1)]);
    const first = take(s, 0); s = first.session;
    s = answered(s, first.card!, 1, result({ delay_seconds: 60, status: "learning", preview: { again: 60, hard: 90, good: 600, easy: 345600 } }), 0, 800, 300);
    const t = take(s, 1_000);
    expect(t.card?.id).toBe(1);
    expect(t.card?.preview.good).toBe(600);                                                // the buttons show the next step, not the old one
  });

  it("lets a word go when it is due much later or the answer was not saved", () => {
    let s = startSession([card(1), card(2)]);
    const a = take(s, 0); s = a.session;
    s = answered(s, a.card!, 3, result({ delay_seconds: 86400, status: "young" }), 0, 100, 100);
    const b = take(s, 0); s = b.session;
    s = answered(s, b.card!, 1, null, 0, 100, 100);
    expect(take(s, 10 ** 9).card).toBeNull();
    expect(s.log).toHaveLength(2);
  });

  it("keeps a forgotten word in the session for its 10 minute relearning step", () => {
    let s = startSession([card(1)]);
    const a = take(s, 0); s = a.session;
    s = answered(s, a.card!, 1, result({ delay_seconds: 600, status: "relearning", lapses: 1 }), 0, 100, 100);
    expect(remaining(s)).toBe(1);
    expect(take(s, 5).card?.lapses).toBe(1);
  });
});

describe("summary and formats", () => {
  const entry = (id: number, grade: Grade, think: number) => ({ id, word: `w${id}`, grade, think_ms: think, rate_ms: 100 });
  it("totals the grades, accuracy, time, slowest words and the missed ones", () => {
    const s = summarize([entry(1, 3, 2000), entry(2, 1, 9000), entry(2, 3, 3000), entry(3, 4, 500), entry(4, 2, 4000)]);
    expect(s.answers).toBe(5);
    expect(s.words).toBe(4);
    expect(s.counts).toEqual({ 1: 1, 2: 1, 3: 2, 4: 1 });
    expect(s.accuracy).toBeCloseTo(0.8);
    expect(s.avgThinkMs).toBe(3700);
    expect(s.slowest.map((w) => w.word)).toEqual(["w2", "w4", "w1"]);
    expect(s.missed).toEqual([{ id: 2, word: "w2" }]);
  });
  it("is empty and not a division by zero with no answers", () => {
    expect(summarize([])).toMatchObject({ answers: 0, accuracy: 0, avgThinkMs: 0, slowest: [], missed: [] });
  });
  it("names delays in the biggest unit that fits", () => {
    expect([30, 60, 600, 7200, 86400, 3 * 86400, 21 * 86400, 90 * 86400].map((s) => delayParts(s))).toEqual([
      { n: 0, unit: "lt1m" }, { n: 1, unit: "m" }, { n: 10, unit: "m" }, { n: 2, unit: "h" }, { n: 1, unit: "d" }, { n: 3, unit: "d" }, { n: 3, unit: "w" }, { n: 3, unit: "mo" }]);
  });
  it("formats times taken", () => {
    expect([formatMs(3200), formatMs(450), formatMs(65_000)]).toEqual(["3.2s", "0.5s", "1m 05s"]);
  });
});
