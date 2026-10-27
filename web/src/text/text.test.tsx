import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ALICE, err, LANGS, mockApi, renderApp } from "../test/helpers";

afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });

const W = (id: number, word: string, meaning: string | null = null) => ({ id, language: "en", word, meaning, set_id: null, created_at: "2026-01-01T00:00:00Z" });
const page = (items: ReturnType<typeof W>[]) => ({ items, total: items.length, limit: 50, offset: 0 });
const OPTIONS = { types: ["narration", "dialogue"], topics: [] };
const REPORT = { rules_version: 4, status: "pass", language: { requested: "en", ok: true, verdict: "english" }, structure: { ok: true, leaked_plan: false, units: 4 }, vocabulary: { mode: "strict", ok: true, outside: [], outside_count: 0, limit: 5 }, read_seconds: 6 };
const STORY = { story: "Ana: Hello.\nBen: Hi.", language: "en", story_type: "dialogue", topic: null, report: REPORT, words_total: 3, words_used: 3 };
const base = { "GET /me": ALICE, "GET /languages": LANGS, "GET /sets": { items: [], general_count: 2, total_count: 2 } };
const callsTo = (calls: ReturnType<typeof mockApi>["calls"], path: string) => calls.filter((c) => c.method === "POST" && c.path === path);

describe("pronunciation on the vocabulary page", () => {
  it("asks only when switched on, for the words on the page, and shows each reading with its kind", async () => {
    const { calls } = mockApi({ ...base, "GET /words": page([W(1, "bread"), W(2, "water")]),
      "POST /pronounce": { kind: "ipa", approximate: true, items: [{ text: "bread", reading: "/brɛd/" }, { text: "water", reading: "/ˈwɔtər/" }] } });
    renderApp("/vocabulary");
    await screen.findByText("bread");
    expect(callsTo(calls, "/pronounce")).toHaveLength(0);
    await userEvent.click(screen.getByRole("button", { name: "Show pronunciation" }));
    expect(await screen.findByText("/brɛd/")).toBeInTheDocument();
    expect(screen.getByText("IPA")).toBeInTheDocument();
    expect(screen.getByText(/a guide, not a dictionary/)).toBeInTheDocument();
    expect(callsTo(calls, "/pronounce")[0].body).toEqual({ language: "en", texts: ["bread", "water"] });
    await userEvent.click(screen.getByRole("button", { name: "Hide pronunciation" }));
    expect(screen.queryByText("/brɛd/")).not.toBeInTheDocument();
  });

  it("shows the server's message when the tutor can't write it", async () => {
    mockApi({ ...base, "GET /words": page([W(1, "bread")]), "POST /pronounce": err(502, "ai_failed", "The tutor couldn't write the pronunciation. Please try again in a moment.") });
    renderApp("/vocabulary");
    await screen.findByText("bread");
    await userEvent.click(screen.getByRole("button", { name: "Show pronunciation" }));
    expect(await screen.findByText(/couldn't write the pronunciation/)).toBeInTheDocument();
  });
});

describe("translating selected words", () => {
  it("sends the selected words as a word list to the chosen language and shows the pairs", async () => {
    const { calls } = mockApi({ ...base, "GET /words": page([W(1, "bread"), W(2, "water"), W(3, "house")]),
      "POST /translate": { target_language: "es", items: [{ text: "bread", translation: "pan" }, { text: "house", translation: null }] } });
    renderApp("/vocabulary");
    await userEvent.click(await screen.findByLabelText("Select bread"));
    await userEvent.click(screen.getByLabelText("Select house"));
    await userEvent.click(screen.getByRole("button", { name: "Translate the selected words" }));
    await userEvent.click(screen.getByRole("button", { name: "Translate" }));
    expect(await screen.findByText("pan")).toBeInTheDocument();
    expect(screen.getByText("(no translation came back)")).toBeInTheDocument();
    expect(callsTo(calls, "/translate")[0].body).toEqual({ language: "en", target_language: "es", texts: ["bread", "house"], words: true });
  });
});

describe("pronunciation and translation of a story", () => {
  async function made() {
    const mocks = mockApi({ ...base, "GET /stories/options": OPTIONS, "POST /stories/generate": STORY,
      "POST /pronounce": { kind: "ipa", approximate: true, items: [{ text: "Ana: Hello.", reading: "/ˈænə həˈloʊ/" }, { text: "Ben: Hi.", reading: "/bɛn haɪ/" }] },
      "POST /translate": { target_language: "es", items: [{ text: "Ana: Hello.", translation: "Ana: Hola." }, { text: "Ben: Hi.", translation: "Ben: Hola." }] } });
    renderApp("/studio");
    await userEvent.click(await screen.findByRole("button", { name: "Make a story" }));
    await screen.findByText(/Ana: Hello\./);
    return mocks;
  }

  it("shows the story line by line with its reading", async () => {
    const { calls } = await made();
    await userEvent.click(screen.getByRole("button", { name: "Show pronunciation" }));
    expect(await screen.findByText("/ˈænə həˈloʊ/")).toBeInTheDocument();
    expect(callsTo(calls, "/pronounce")[0].body).toEqual({ language: "en", texts: ["Ana: Hello.", "Ben: Hi."] });
  });

  it("translates the story's lines into another language and says nothing is saved", async () => {
    const { calls } = await made();
    await userEvent.click(screen.getByRole("button", { name: "Translate" }));
    expect(screen.getByText(/It is not saved/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Translate" }));          // the toggle now says "Hide translation"
    await waitFor(() => expect(callsTo(calls, "/translate")).toHaveLength(1));
    expect(callsTo(calls, "/translate")[0].body).toEqual({ language: "en", target_language: "es", texts: ["Ana: Hello.", "Ben: Hi."], words: false });
    expect(await screen.findByText("Ben: Hola.")).toBeInTheDocument();
  });
});
