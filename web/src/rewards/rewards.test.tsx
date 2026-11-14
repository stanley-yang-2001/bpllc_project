import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ALICE, LANGS, mockApi, renderApp } from "../test/helpers";

afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });

const BADGES = [
  { id: "first_answer", earned: true, have: 1, target: 1 },
  { id: "known_10", earned: true, have: 10, target: 10 },
  { id: "known_50", earned: false, have: 30, target: 50 },
  { id: "streak_3", earned: true, have: 3, target: 3 },
  { id: "streak_7", earned: false, have: 5, target: 7 },
  { id: "first_story", earned: false, have: 0, target: 1 },
];
const REWARDS = {
  show_rewards: true,
  streak: { days: 5, alive: true, practised_today: false, rest_available: true, rest_used_on: null, best: 8 },
  goal: { target: 10, done: 4, reached: false, left: 6 },
  week: { days_practised: 4, answers: 40, words_learned: 7, stories_saved: 2, due_now: 12, new_words: 3 },
  known_words: 30,
  badges: BADGES,
  next_badge: BADGES[4],
};
const base = { "GET /me": ALICE, "GET /languages": LANGS, "GET /words": { items: [{ id: 1 }], total: 1, limit: 1, offset: 0 }, "GET /practice/rewards": REWARDS };

describe("progress and rewards", () => {
  it("Home shows the goal, the streak with its rest day, the week and the next badge", async () => {
    mockApi(base);
    renderApp("/");
    const card = await screen.findByTestId("rewards-card");
    expect(within(card).getByRole("progressbar", { name: "Today's goal" })).toHaveAttribute("aria-valuenow", "4");
    expect(within(card).getByText("4 of 10 answers")).toBeInTheDocument();
    expect(within(card).getByText("6 more to reach today's goal")).toBeInTheDocument();
    expect(within(card).getByText("5-day streak")).toBeInTheDocument();
    expect(within(card).getByText("Practise today to keep your streak going.")).toBeInTheDocument();
    expect(within(card).getByText("A missed day won't break your streak this week.")).toBeInTheDocument();
    expect(within(card).getByText("7")).toBeInTheDocument();                                     // words learned this week
    expect(within(card).getByText(/Next badge:/)).toBeInTheDocument();
    expect(within(card).getByText("Practise 7 days in a row.")).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: "Practise now" })).toHaveAttribute("href", "/practice");
  });

  it("says the goal is reached with a word, not only a colour", async () => {
    mockApi({ ...base, "GET /practice/rewards": { ...REWARDS, goal: { target: 10, done: 12, reached: true, left: 0 }, streak: { ...REWARDS.streak, practised_today: true } } });
    renderApp("/");
    expect(await screen.findByText("Daily goal reached. Nice work!")).toBeInTheDocument();
    expect(screen.getByText("You practised today. See you tomorrow!")).toBeInTheDocument();
  });

  it("the top bar always shows the streak and goal, and links to the progress page", async () => {
    mockApi(base);
    renderApp("/vocabulary");
    const chip = await screen.findByRole("link", { name: /Streak and today's goal: 5-day streak, 4 of 10 answers/ });
    expect(chip).toHaveAttribute("href", "/progress");
  });

  it("the progress page lists every badge: earned ones marked, the others with how far along and what to do", async () => {
    mockApi(base);
    renderApp("/progress");
    expect(await screen.findByTestId("badge-known_10")).toHaveAttribute("data-earned", "true");
    expect(within(screen.getByTestId("badge-known_10")).getByText("Earned")).toBeInTheDocument();
    const todo = screen.getByTestId("badge-known_50");
    expect(todo).toHaveAttribute("data-earned", "false");
    expect(within(todo).getByText("50 words known")).toBeInTheDocument();
    expect(within(todo).getByText("Get 50 words to Known.")).toBeInTheDocument();
    expect(within(todo).getByText("30 of 50")).toBeInTheDocument();
    expect(within(screen.getByTestId("badge-first_story")).getByText("Save a story to your Library.")).toBeInTheDocument();
  });

  it("a learner who turned rewards off sees none, and the progress page says where to turn them on", async () => {
    mockApi({ ...base, "GET /me": { ...ALICE, preferences: { active_language: null, ui_follows_study_language: false, chat_in_study_language: false, meaning_mode: "native", theme: "light", custom_colors: null, daily_goal: 10, show_rewards: false } }, "GET /practice/rewards": { ...REWARDS, show_rewards: false } });
    renderApp("/");
    expect(await screen.findByText(/Welcome, Alice/)).toBeInTheDocument();
    await vi.waitFor(() => expect(screen.queryByTestId("rewards-card")).toBeNull());
    expect(screen.queryByRole("link", { name: /Streak and today's goal/ })).toBeNull();
  });

  it("a failed request hides the rewards without breaking the page", async () => {
    mockApi({ "GET /me": ALICE, "GET /languages": LANGS, "GET /words": { items: [{ id: 1 }], total: 1, limit: 1, offset: 0 } });
    renderApp("/");
    expect(await screen.findByText(/Welcome, Alice/)).toBeInTheDocument();
    await vi.waitFor(() => expect(screen.queryByTestId("rewards-card")).toBeNull());
  });

  it("says once when a new badge was earned, and says nothing the first time on a device", async () => {
    mockApi(base);
    renderApp("/vocabulary");
    await screen.findByRole("link", { name: /Streak and today's goal/ });
    expect(screen.queryByText(/New badge:/)).toBeNull();                                            // first look: only recorded
    expect(JSON.parse(localStorage.getItem("tutor:badges-seen:1")!)).toEqual(["first_answer", "known_10", "streak_3"]);
    localStorage.setItem("tutor:badges-seen:1", JSON.stringify(["first_answer", "known_10"]));
    renderApp("/vocabulary");
    expect(await screen.findByText("New badge: 3-day streak")).toBeInTheDocument();
  });

  it("Settings sets the daily goal and can hide rewards", async () => {
    const { calls } = mockApi({ ...base, "GET /words": { items: [], total: 0, limit: 1, offset: 0 }, "PATCH /me/preferences": (c: { body: unknown }) => ({ json: { active_language: null, ui_follows_study_language: false, chat_in_study_language: false, meaning_mode: "native", theme: "system", custom_colors: null, daily_goal: 10, show_rewards: true, ...(c.body as object) } }) });
    renderApp("/settings");
    const goal = await screen.findByLabelText("Daily goal (answers a day)");
    await userEvent.selectOptions(goal, "20");
    await userEvent.click(screen.getByRole("checkbox", { name: "Show my streak, goal and badges" }));
    await vi.waitFor(() => expect(calls.filter((c) => c.method === "PATCH").map((c) => c.body)).toEqual(expect.arrayContaining([expect.objectContaining({ daily_goal: 20 }), expect.objectContaining({ show_rewards: false })])));
  });
});
