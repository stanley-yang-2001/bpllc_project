import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ALICE, DIFFICULTY, LANGS, mockApi, renderApp, renderIn } from "../test/helpers";
import { WordTable } from "../vocab/WordTable";

afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });

const EXPOSURE = { answers: 3, stories: 2, met: 5, last_answered: "2026-11-20T10:00:00Z" };
const WORD = { id: 7, language: "en", word: "bread", meaning: "pan", pos: null, set_id: null, created_at: "2026-11-01T00:00:00Z", picture: null, exposure: EXPOSURE };
const WORDS = { items: [WORD], total: 1, limit: 1, offset: 0 };
const base = { "GET /me": ALICE, "GET /languages": LANGS, "GET /words": WORDS };

describe("the Met column", () => {
  it("shows how often a word has been met, with the split on hover and a spoken count", () => {
    renderIn(<WordTable words={[WORD as never]} language="en" selected={new Set()} onToggle={() => {}} onToggleAll={() => {}} readings={new Map()} showReadings={false} setNames={null} />);
    expect(screen.getByRole("columnheader", { name: "Met" })).toBeInTheDocument();
    const count = screen.getByLabelText("5 times met");
    expect(count).toHaveTextContent("5");
    expect(count).toHaveAttribute("title", "3 answers in practice, 2 saved stories");
  });

  it("leaves the cell empty when the server sent no count", () => {
    renderIn(<WordTable words={[{ ...WORD, exposure: null } as never]} language="en" selected={new Set()} onToggle={() => {}} onToggleAll={() => {}} readings={new Map()} showReadings={false} setNames={null} />);
    expect(screen.queryByLabelText(/times met/)).not.toBeInTheDocument();
  });
});

describe("the word of the day on Home", () => {
  it("shows today's word, its meaning and how often it has been met", async () => {
    mockApi({ ...base, "GET /words/today?language=en": { date: "2026-11-24", word: WORD } });
    renderApp("/");
    const card = await screen.findByRole("region", { name: "Word of the day" });
    expect(within(card).getByText("bread")).toBeInTheDocument();
    expect(within(card).getByText("pan")).toBeInTheDocument();
    expect(within(card).getByText(/You have met it 5 times\./)).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: "Practise" })).toHaveAttribute("href", "/practice");
    expect(within(card).getByRole("button", { name: "Add a picture for bread" })).toBeInTheDocument();
  });

  it("says so when the word has not been met, and when it has no meaning yet", async () => {
    mockApi({ ...base, "GET /words/today?language=en": { date: "2026-11-24", word: { ...WORD, meaning: null, exposure: { answers: 0, stories: 0, met: 0, last_answered: null } } } });
    renderApp("/");
    const card = await screen.findByRole("region", { name: "Word of the day" });
    expect(within(card).getByText("No meaning saved yet")).toBeInTheDocument();
    expect(within(card).getByText(/You have not met it yet\./)).toBeInTheDocument();
  });

  it("shows nothing when there is no word yet or the request fails", async () => {
    mockApi({ ...base, "GET /words/today?language=en": { date: "2026-11-24", word: null } });
    const first = renderApp("/");
    await screen.findByRole("heading", { level: 1 });
    await waitFor(() => expect(screen.queryByRole("region", { name: "Word of the day" })).not.toBeInTheDocument());
    first.ui.unmount();
    mockApi({ ...base });                                   // no mock for /words/today: the server answers 404
    renderApp("/");
    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByRole("region", { name: "Word of the day" })).not.toBeInTheDocument();
  });
});

describe("the story focus in Story Studio", () => {
  const OPTIONS = { types: ["story"], topics: [], difficulty: DIFFICULTY };
  const REPORT = {
    rules_version: 1, status: "pass", language: { requested: "en", ok: true, verdict: "english" }, structure: { ok: true, leaked_plan: false, units: 4 },
    vocabulary: { mode: "strict", ok: true, outside: [], outside_count: 0, limit: 5 }, read_seconds: 6,
  };
  const STORY = { story: "Ana: Hello.\nBen: Hello.", language: "en", story_type: "story", topic: null, report: REPORT, words_total: 8, words_used: 8, focus: "least_met", focus_matched: 8 };
  const sent = (calls: ReturnType<typeof mockApi>["calls"]) => calls.filter((c) => c.method === "POST" && c.path === "/stories/generate");

  it("offers four focuses, all words by default, and sends none unless one is chosen", async () => {
    const { calls } = mockApi({ ...base, "GET /stories/options": OPTIONS, "POST /stories/generate": { ...STORY, focus: "all", focus_matched: null } });
    renderApp("/studio");
    const focus = await screen.findByLabelText("Build the story around");
    expect(focus).toHaveValue("all");
    expect(within(focus).getAllByRole("option").map((o) => o.textContent)).toEqual(["All my words", "Words I have met least", "Words due soon", "New words I have not practised"]);
    await userEvent.click(screen.getByRole("button", { name: "Make a story" }));
    await waitFor(() => expect(sent(calls)).toHaveLength(1));
    expect(sent(calls)[0].body).not.toHaveProperty("focus");
    expect(screen.queryByText(/Built around/)).not.toBeInTheDocument();
  });

  it("sends the chosen focus and says what the story was built around", async () => {
    const { calls } = mockApi({ ...base, "GET /stories/options": OPTIONS, "POST /stories/generate": STORY });
    renderApp("/studio");
    await userEvent.selectOptions(await screen.findByLabelText("Build the story around"), "least_met");
    await userEvent.click(screen.getByRole("button", { name: "Make a story" }));
    await waitFor(() => expect(sent(calls)).toHaveLength(1));
    expect(sent(calls)[0].body).toMatchObject({ language: "en", focus: "least_met" });
    expect(await screen.findByText("Built around: Words I have met least")).toBeInTheDocument();
  });
});
