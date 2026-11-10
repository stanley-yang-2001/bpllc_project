import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ALICE, err, LANGS, mockApi, renderApp } from "../test/helpers";

afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });

const day = (n: number) => `2026-11-${String(9 + n).padStart(2, "0")}`;
const STATS = {
  language: "en", words: 20, new: 5, learning: 3, relearning: 1, young: 7, mature: 4, due_now: 6, leeches: 2, reviews_30d: 40, accuracy_30d: 0.85,
  retention_30d: 0.9, avg_think_ms: 3200, median_think_ms: 2800, avg_rate_ms: 700, studied_seconds_30d: 600, today_reviews: 12, total_reviews: 212, total_words_practised: 18, total_days: 9, total_accuracy: 0.82, total_retention: 0.88, total_avg_think_ms: 3400, total_studied_seconds: 3600,
  days: [{ day: day(0), reviews: 12, correct: 10, avg_think_ms: 3000 }], forecast: [0, 1, 2, 3, 4, 5, 6].map((n) => ({ day: day(n), due: n === 0 ? 6 : n })),
};
const HARD = { typical_think_ms: 2800, items: [
  { id: 4, word: "water", meaning: "a drink", score: 82, reasons: ["often_missed", "slow"], reviews: 6, miss_rate: 0.67, avg_think_ms: 9100, lapses: 3, ease: 1.9, status: "relearning", due_at: null },
  { id: 9, word: "bread", meaning: null, score: 41, reasons: [], reviews: 3, miss_rate: 0.33, avg_think_ms: null, lapses: 1, ease: 2.3, status: "young", due_at: null },
] };
const PROGRESS = { language: "en", new: 5, learning: 4, known: 11, due: 6, streak: 2, practised_today: true };
const base = { "GET /me": ALICE, "GET /languages": LANGS, "GET /stories": { items: [], total: 0, limit: 100, offset: 0 }, "GET /practice/progress": PROGRESS };

describe("study statistics and hardest words", () => {
  it("shows retention, accuracy, answer time, study time, today, stages and the forecast", async () => {
    mockApi({ ...base, "GET /practice/stats": STATS, "GET /practice/hardest": HARD });
    renderApp("/practice");
    expect(await screen.findByText("Your memory")).toBeInTheDocument();
    for (const [label, value] of [["Retention", "90%"], ["Not missed", "85%"], ["Time to answer", "3.2s"], ["Studied (30 days)", "10 min"], ["Answers today", "12"]])
      expect(screen.getByText(label).nextElementSibling).toHaveTextContent(value);
    expect(screen.getByText("Relearning 1")).toBeInTheDocument();
    expect(screen.getByText("Mature 4")).toBeInTheDocument();
    expect(screen.getByText("2 words you keep forgetting")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem").filter((li) => li.getAttribute("aria-label")?.includes(":"))).toHaveLength(7);
  });

  it("lists the hardest words with why and how long they take, and practises exactly those words", async () => {
    const flash = { items: [], total: 0, selection: 0, due: 0, new: 0 };
    const { calls } = mockApi({ ...base, "GET /practice/stats": STATS, "GET /practice/hardest": HARD, "GET /practice/flashcards": flash });
    renderApp("/practice");
    expect(await screen.findByText("Your hardest words")).toBeInTheDocument();
    expect(screen.getByText("82/100")).toBeInTheDocument();
    expect(screen.getByText(/6 answers · 67% missed · 9.1s on average · often missed, slow to answer/)).toBeInTheDocument();
    expect(screen.getByText("3 answers · 33% missed")).toBeInTheDocument();                   // no timing yet for this one
    await userEvent.click(screen.getByRole("button", { name: "Practise these" }));
    await screen.findByText("No flashcards yet");
    expect(calls.find((c) => c.path.startsWith("/practice/flashcards"))!.path).toBe("/practice/flashcards?language=en&scope=ids&ids=4%2C9");
  });

  it("explains an empty hardest list, and a learner with no answers yet", async () => {
    mockApi({ ...base, "GET /practice/stats": { ...STATS, reviews_30d: 0, avg_think_ms: null, retention_30d: null, accuracy_30d: null }, "GET /practice/hardest": { items: [], typical_think_ms: null } });
    renderApp("/practice");
    expect(await screen.findByText(/No answers yet/)).toBeInTheDocument();
    expect(screen.getByText(/A word needs at least two answers/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Practise these" })).not.toBeInTheDocument();
  });

  it("asks for the statistics of the chosen sets, and hides itself when they cannot be loaded", async () => {
    const sets = { items: [{ id: 7, name: "Food", language: "en", count: 2 }], general_count: 3, total_count: 5 };
    const { calls } = mockApi({ ...base, "GET /sets": sets, "GET /practice/stats": STATS, "GET /practice/hardest": HARD });
    const { ui } = renderApp("/practice");
    await userEvent.click(await screen.findByRole("button", { name: /^Food/ }));
    await userEvent.click(screen.getByRole("button", { name: /^General/ }));
    await screen.findByText("Your memory");
    expect(calls.some((c) => c.path === "/practice/stats?language=en&set=general%2C7")).toBe(true);
    expect(calls.some((c) => c.path === "/practice/hardest?language=en&set=general%2C7&limit=8")).toBe(true);
    expect(calls.some((c) => c.path === "/practice/progress?language=en&set=general%2C7")).toBe(true);
    ui.unmount();
    mockApi({ ...base, "GET /practice/stats": err(500, "internal", "boom"), "GET /practice/hardest": err(500, "internal", "boom") });
    renderApp("/practice");
    expect(await screen.findByRole("button", { name: "Study what's due" })).toBeInTheDocument();
    expect(screen.queryByText("Your memory")).not.toBeInTheDocument();
  });
});
