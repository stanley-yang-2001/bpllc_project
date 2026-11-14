import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ALICE, LANGS, mockApi, renderApp } from "../test/helpers";
import { gardenPlots, MAX_PLOTS } from "./garden";

afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });

const R = (over: Record<string, unknown> = {}) => ({
  show_rewards: true, streak: { days: 5, alive: true, practised_today: false, rest_available: true, rest_used_on: null, best: 8 },
  goal: { target: 10, done: 4, reached: false, left: 6 }, week: { days_practised: 4, answers: 40, words_learned: 7, stories_saved: 2, due_now: 12, new_words: 3 },
  known_words: 30, comeback: null, challenge: { id: "learn_words", have: 4, target: 10, done: false, ends_on: "2026-11-15" }, garden: { seeds: 10, sprouts: 8, trees: 12 },
  records: { best_day: null, longest_run: 0, fastest_ms: null, best_week_learned: 0 }, story_words: { used: 0, total: 0 },
  badges: [{ id: "first_answer", earned: true, have: 1, target: 1 }], next_badge: null, ...over });
const base = (rewards: unknown) => ({ "GET /me": ALICE, "GET /languages": LANGS, "GET /words": { items: [{ id: 1 }], total: 1, limit: 1, offset: 0 }, "GET /practice/rewards": rewards });

describe("garden pictures", () => {
  it("draws trees first, then sprouts, then seeds", () => {
    expect(gardenPlots({ seeds: 1, sprouts: 2, trees: 3 })).toEqual(["trees", "trees", "trees", "sprouts", "sprouts", "seeds"]);
    expect(gardenPlots({ seeds: 0, sprouts: 0, trees: 0 })).toEqual([]);
  });
  it("shrinks a big vocabulary but keeps every stage that has words", () => {
    const plots = gardenPlots({ seeds: 5000, sprouts: 3, trees: 10 });
    expect(plots.length).toBeLessThanOrEqual(MAX_PLOTS + 2);
    expect(new Set(plots)).toEqual(new Set(["trees", "sprouts", "seeds"]));
  });
});

describe("weekly challenge and garden", () => {
  it("Home shows this week's challenge with its progress and when it ends", async () => {
    mockApi(base(R()));
    renderApp("/");
    const box = await screen.findByTestId("challenge");
    expect(within(box).getByText("Learn 10 new words")).toBeInTheDocument();
    expect(within(box).getByText("(4 of 10)")).toBeInTheDocument();
    expect(within(box).getByRole("progressbar", { name: "This week's challenge" })).toHaveAttribute("aria-valuenow", "4");
    expect(within(box).getByText("Ends Sunday")).toBeInTheDocument();
  });

  it("a finished challenge says so", async () => {
    mockApi(base(R({ challenge: { id: "practise_days", have: 5, target: 5, done: true, ends_on: "2026-11-15" } })));
    renderApp("/");
    const box = await screen.findByTestId("challenge");
    expect(within(box).getByText("Practise on 5 different days")).toBeInTheDocument();
    expect(within(box).getByText("Challenge complete! A new one starts Monday.")).toBeInTheDocument();
  });

  it("the progress page shows the word garden with the counts of each stage", async () => {
    mockApi(base(R()));
    renderApp("/progress");
    const g = await screen.findByTestId("garden-card");
    expect(within(g).getByText("Trees (known)").closest("div")).toHaveTextContent("12");
    expect(within(g).getByText("Sprouts (learning)").closest("div")).toHaveTextContent("8");
    expect(within(g).getByText("Seeds (not practised yet)").closest("div")).toHaveTextContent("10");
    expect(within(g).getByTestId("garden-plots").children).toHaveLength(30);
  });

  it("an empty garden invites the learner to add words", async () => {
    mockApi(base(R({ garden: { seeds: 0, sprouts: 0, trees: 0 } })));
    renderApp("/progress");
    expect(await screen.findByText("Add words to plant your first seeds.")).toBeInTheDocument();
  });

  it("says so, with a bigger effect, when a practice answer finishes the challenge", async () => {
    const P = { again: 60, hard: 90, good: 600, easy: 345600 };
    const cards = { items: [{ id: 1, word: "water", meaning: "a drink", status: "new", ease: 2.5, interval_days: 0, lapses: 0, reps: 0, leech: false, due_at: null, preview: P }], total: 1, selection: 1, due: 0, new: 1 };
    let calls = 0;
    mockApi({ ...base(null), "GET /practice/flashcards": cards,
      "GET /practice/rewards": () => ({ json: R({ challenge: { id: "answer_cards", have: calls++ === 0 ? 99 : 100, target: 100, done: calls > 1, ends_on: "2026-11-15" } }) }),
      "POST /practice/reviews": (c: any) => ({ json: { results: c.body.reviews.map((r: any) => ({ word_id: r.word_id, delay_seconds: 600, status: "learning", counted: true, correct: true, box: 1, ease: 2.5, interval_days: 0, lapses: 0, preview: P })) } }) });
    renderApp("/practice");
    await userEvent.click(await screen.findByRole("button", { name: "Study what's due" }));
    await userEvent.click(await screen.findByRole("button", { name: "Show answer" }));
    await userEvent.click(screen.getByRole("button", { name: /^Good/ }));
    expect((await screen.findAllByText("Weekly challenge complete!")).length).toBeGreaterThan(0);
    expect(screen.getByTestId("celebration")).toHaveAttribute("data-level", "4");
  });
});
