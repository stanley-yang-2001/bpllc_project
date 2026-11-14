import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Entry } from "../practice/session";
import { ALICE, LANGS, mockApi, renderApp } from "../test/helpers";
import { badgeLevel, milestoneFor, PARTICLES, runLength } from "./effects";

afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });

const log = (...grades: number[]): Entry[] => grades.map((grade, i) => ({ id: i, word: `w${i}`, grade: grade as 1, think_ms: 1, rate_ms: 1 }));
const many = (n: number, g = 3) => log(...Array<number>(n).fill(g));

describe("celebration levels", () => {
  it("counts the run of answers that were not Again", () => {
    expect(runLength(log(3, 1, 2, 4))).toBe(2);
    expect(runLength(log(1))).toBe(0);
  });
  it("gets bigger with the milestone", () => {
    expect(milestoneFor(many(2))).toBeNull();
    expect(milestoneFor(many(3))).toEqual({ level: 1, kind: "combo", n: 3 });
    expect(milestoneFor(many(5))?.level).toBe(2);
    expect(milestoneFor(many(10))?.level).toBe(3);
    expect(milestoneFor(many(25))?.level).toBe(4);
    expect(milestoneFor(many(50))?.level).toBe(5);
  });
  it("a card count counts even when the run was broken, and the bigger of two wins", () => {
    expect(milestoneFor([...many(24), ...log(1)].slice(0, 9).concat(log(1)))).toEqual({ level: 2, kind: "cards", n: 10 });
    expect(milestoneFor(many(100))?.level).toBe(5);
  });
  it("an Again on a milestone card gives no run celebration", () => {
    expect(milestoneFor([...many(2), ...log(1)])).toBeNull();
  });
  it("bigger levels draw more pieces, and the biggest badges are the biggest levels", () => {
    expect(PARTICLES.slice(1)).toEqual([...PARTICLES.slice(1)].sort((a, b) => a - b));
    expect(badgeLevel("streak_30")).toBeGreaterThan(badgeLevel("streak_3"));
    expect(badgeLevel("known_250")).toBeGreaterThan(badgeLevel("known_10"));
  });
});

const PREVIEW = { again: 60, hard: 90, good: 600, easy: 345600 };
const card = (id: number) => ({ id, word: `word${String.fromCharCode(97 + id)}`, meaning: "m", status: "new", ease: 2.5, interval_days: 0, lapses: 0, reps: 0, leech: false, due_at: null, preview: PREVIEW });
const CARDS = (n: number) => ({ items: Array.from({ length: n }, (_, i) => card(i + 1)), total: n, selection: n, due: 0, new: n });
const RESULT = (word_id: number) => ({ word_id, delay_seconds: 86400, status: "young", counted: true, correct: true, box: 2, ease: 2.5, interval_days: 1, lapses: 0, preview: PREVIEW });
const REWARDS = (show: boolean) => ({ show_rewards: show, streak: { days: 0, alive: false, practised_today: false, rest_available: false, rest_used_on: null, best: 0 },
  goal: { target: 10, done: 0, reached: false, left: 10 }, week: { days_practised: 0, answers: 0, words_learned: 0, stories_saved: 0, due_now: 0, new_words: 0 }, known_words: 0, comeback: null, challenge: { id: "answer_cards", have: 0, target: 100, done: false, ends_on: "2026-11-15" }, garden: { seeds: 0, sprouts: 0, trees: 0 }, records: { best_day: null, longest_run: 0, fastest_ms: null, best_week_learned: 0 }, story_words: { used: 0, total: 0 }, badges: [], next_badge: null });
const routes = (n: number, show = true) => ({ "GET /me": ALICE, "GET /languages": LANGS, "GET /stories": { items: [], total: 0, limit: 100, offset: 0 }, "GET /practice/rewards": REWARDS(show),
  "GET /practice/flashcards": CARDS(n), "POST /practice/reviews": (c: any) => ({ json: { results: c.body.reviews.map((r: any) => RESULT(r.word_id)) } }) });

async function answer(n: number) {
  for (let i = 0; i < n; i++) {
    await userEvent.click(await screen.findByRole("button", { name: "Show answer" }));
    await userEvent.click(screen.getByRole("button", { name: /^Good/ }));
  }
}

describe("effects while practising flashcards", () => {
  it("says '3 in a row!' as a small label, then something bigger at 10", async () => {
    mockApi(routes(10));
    renderApp("/practice");
    await userEvent.click(await screen.findByRole("button", { name: "Study what's due" }));
    await answer(3);
    expect(await screen.findByText("3 in a row!")).toBeInTheDocument();
    expect(screen.getByTestId("celebration")).toHaveAttribute("data-level", "1");
    await answer(7);
    await waitFor(() => expect(screen.getByTestId("celebration")).toHaveAttribute("data-level", "3"));
    expect(screen.getByText("10 in a row!")).toBeInTheDocument();
    expect(screen.getByTestId("celebration").querySelectorAll(".fx-piece")).toHaveLength(PARTICLES[3]);
  });

  it("shows nothing when the learner turned rewards off", async () => {
    mockApi(routes(3, false));
    renderApp("/practice");
    await userEvent.click(await screen.findByRole("button", { name: "Study what's due" }));
    await answer(3);
    expect(screen.queryByTestId("celebration")).not.toBeInTheDocument();
  });

  it("with reduced motion only the label shows, no moving pieces", async () => {
    vi.stubGlobal("matchMedia", (q: string) => ({ matches: q.includes("reduce"), media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, onchange: null, dispatchEvent: () => false }));
    mockApi(routes(5));
    renderApp("/practice");
    await userEvent.click(await screen.findByRole("button", { name: "Study what's due" }));
    await answer(5);
    expect(await screen.findByText("5 in a row!")).toBeInTheDocument();
    expect(screen.getByTestId("celebration").querySelectorAll(".fx-piece")).toHaveLength(0);
  });
});
