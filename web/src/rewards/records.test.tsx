import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ALICE, LANGS, mockApi, renderApp } from "../test/helpers";
import { beaten, remember } from "./records";

afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });

const R = (over: Record<string, unknown> = {}) => ({
  show_rewards: true, streak: { days: 5, alive: true, practised_today: false, rest_available: true, rest_used_on: null, best: 8 },
  goal: { target: 10, done: 4, reached: false, left: 6 }, week: { days_practised: 4, answers: 40, words_learned: 7, stories_saved: 2, due_now: 12, new_words: 3 },
  known_words: 30, comeback: null, challenge: { id: "learn_words", have: 4, target: 10, done: false, ends_on: "2026-11-15" }, garden: { seeds: 10, sprouts: 8, trees: 12 }, records: { best_day: { value: 34, day: "2026-11-10" }, longest_run: 18, fastest_ms: 2400, best_week_learned: 9 },
  story_words: { used: 12, total: 30 }, badges: [{ id: "first_answer", earned: true, have: 1, target: 1 }], next_badge: null, ...over });
const base = (rewards: unknown) => ({ "GET /me": ALICE, "GET /languages": LANGS, "GET /words": { items: [{ id: 1 }], total: 1, limit: 1, offset: 0 }, "GET /practice/rewards": rewards });
const REC = { best_day: { value: 34, day: "2026-11-10" }, longest_run: 18, fastest_ms: 2400, best_week_learned: 9 };

describe("record comparison", () => {
  it("only a value above the one already seen is a new record, and a lower time is better", () => {
    expect(beaten({ best_day: 30, longest_run: 18, fastest_ms: 3000, best_week_learned: 9 }, REC)).toEqual(["best_day", "fastest_ms"]);
  });
  it("a first-ever value is not news", () => {
    expect(beaten({}, REC)).toEqual([]);
    expect(beaten({ best_day: 30 }, { ...REC, best_day: null })).toEqual([]);
  });
  it("remembers the best seen so far", () => {
    expect(remember({ best_day: 40, fastest_ms: 3000 }, REC)).toMatchObject({ best_day: 40, fastest_ms: 2400, longest_run: 18 });
  });
});

describe("records, words in stories and the comeback bonus", () => {
  it("the progress page shows the learner's records and how many words appear in their stories", async () => {
    mockApi(base(R()));
    renderApp("/progress");
    const rec = await screen.findByTestId("records-card");
    expect(within(rec).getByText("Most answers in a day")).toBeInTheDocument();
    expect(within(rec).getByText("34")).toBeInTheDocument();
    expect(within(rec).getByText("18")).toBeInTheDocument();
    expect(within(rec).getByText("Only you can beat these.")).toBeInTheDocument();
    const sw = screen.getByTestId("storywords-card");
    expect(within(sw).getByText("12 of 30 words appear in a story you saved.")).toBeInTheDocument();
    expect(within(sw).getByRole("progressbar", { name: "Words in your stories" })).toHaveAttribute("aria-valuenow", "12");
  });

  it("a learner with no records yet is told to practise, and no words hides the story card", async () => {
    mockApi(base(R({ records: { best_day: null, longest_run: 0, fastest_ms: null, best_week_learned: 0 }, story_words: { used: 0, total: 0 } })));
    renderApp("/progress");
    expect(await screen.findByText("Practise to set your first records.")).toBeInTheDocument();
    expect(screen.queryByTestId("storywords-card")).not.toBeInTheDocument();
  });

  it("welcomes a learner back after a break, with how many words are ready", async () => {
    mockApi(base(R({ comeback: { days_away: 6, returned: false } })));
    renderApp("/");
    const note = await screen.findByTestId("comeback");
    expect(within(note).getByText("Welcome back!")).toBeInTheDocument();
    expect(within(note).getByText("It's been 6 days. A few answers today start a new streak, and 12 words are ready.")).toBeInTheDocument();
  });

  it("no welcome once they have practised today, or when they never left", async () => {
    mockApi(base(R({ comeback: { days_away: 6, returned: true } })));
    renderApp("/");
    await screen.findByTestId("rewards-card");
    expect(screen.queryByTestId("comeback")).not.toBeInTheDocument();
  });

  it("says a personal record was beaten, once, and nothing the first time on a device", async () => {
    localStorage.setItem("tutor:records-seen:1", JSON.stringify({ seen: { best_day: 30, longest_run: 18, fastest_ms: 2400, best_week_learned: 9 }, told: {} }));
    mockApi(base(R()));
    renderApp("/");
    expect(await screen.findByText("New personal record: Most answers in a day")).toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem("tutor:records-seen:1")!).seen.best_day).toBe(34);
  });

  it("stays silent about records on a first visit", async () => {
    mockApi(base(R()));
    renderApp("/");
    await screen.findByTestId("rewards-card");
    expect(screen.queryByText(/New personal record/)).not.toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem("tutor:records-seen:1")!).seen).toMatchObject({ best_day: 34, longest_run: 18 });
  });
});
