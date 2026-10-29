import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ALICE, err, LANGS, mockApi, renderApp } from "../test/helpers";

let spoken: string[];
let voices: { lang: string; name: string }[];

function installSpeech() {
  spoken = [];
  class FakeUtterance { onend: (() => void) | null = null; onerror: (() => void) | null = null; lang = ""; rate = 1; voice: unknown = null; constructor(public text: string) {} }
  vi.stubGlobal("SpeechSynthesisUtterance", FakeUtterance);
  Object.defineProperty(window, "speechSynthesis", {
    value: { speak: (u: FakeUtterance) => spoken.push(u.text), cancel: () => undefined, getVoices: () => voices },
    configurable: true,
  });
}

beforeEach(() => { voices = [{ lang: "en-US", name: "US English" }]; });
afterEach(() => { vi.unstubAllGlobals(); Reflect.deleteProperty(window, "speechSynthesis"); localStorage.clear(); sessionStorage.clear(); });

const WORDS = { items: [{ id: 1, word: "water", meaning: "a drink" }, { id: 2, word: "café", meaning: null }, { id: 3, word: "bread", meaning: "baked food" }], total: 3 };
const base = { "GET /me": ALICE, "GET /languages": LANGS, "GET /stories": { items: [], total: 0, limit: 100, offset: 0 }, "GET /practice/dictation": WORDS, "POST /practice/answers": { status: 204 } };
const answers = (calls: { method: string; path: string; body: any }[]) => calls.filter((c) => c.method === "POST" && c.path === "/practice/answers").map((c) => c.body.answers[0]);

async function typeAndCheck(text: string) {
  await userEvent.type(await screen.findByLabelText("Your answer"), text);
  await userEvent.click(screen.getByRole("button", { name: "Check" }));
}

describe("dictation", () => {
  it("says the browser can't read aloud, and offers no start button", async () => {
    mockApi(base);
    renderApp("/practice");
    expect(await screen.findByText("This browser can't read aloud, so dictation isn't available here.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start dictation" })).not.toBeInTheDocument();
  });

  it("says there is no voice for the studied language instead of speaking with the wrong one", async () => {
    voices = [{ lang: "ja-JP", name: "Kyoko" }];
    installSpeech();
    mockApi(base);
    renderApp("/practice");
    expect(await screen.findByText(/no read-aloud voice for English/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start dictation" })).not.toBeInTheDocument();
  });

  it("reads the word aloud, marks a right answer ignoring case, and remembers it", async () => {
    installSpeech();
    const { calls } = mockApi(base);
    renderApp("/practice");
    await userEvent.click(await screen.findByRole("button", { name: "Start dictation" }));
    await userEvent.click(await screen.findByRole("button", { name: "Listen" }));
    expect(spoken).toEqual([expect.stringMatching(/./)]);
    expect(calls.find((c) => c.path.startsWith("/practice/dictation"))!.path).toBe("/practice/dictation?language=en&limit=10");
    const heard = spoken[0];
    await typeAndCheck(heard.toUpperCase());
    expect(await screen.findByText("Correct!")).toBeInTheDocument();
    await waitFor(() => expect(answers(calls)).toEqual([{ word_id: WORDS.items.find((w) => w.word === heard)!.id, correct: true }]));
  });

  it("tells a wrong answer from a missing accent, shows the meaning, and totals the score", async () => {
    installSpeech();
    const { calls } = mockApi({ ...base, "GET /practice/dictation": { items: [{ id: 2, word: "café", meaning: null }, { id: 1, word: "water", meaning: "a drink" }], total: 2 } });
    renderApp("/practice");
    await userEvent.click(await screen.findByRole("button", { name: "Start dictation" }));
    await typeAndCheck("cafe");
    expect(await screen.findByText("Almost: check the accents. The word is “café”.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await typeAndCheck("watter");
    expect(await screen.findByText("Not quite. The word is “water”.")).toBeInTheDocument();
    expect(screen.getByText("a drink")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "See result" }));
    expect(await screen.findByText("You got 0 of 2.")).toBeInTheDocument();
    await waitFor(() => expect(answers(calls)).toEqual([{ word_id: 2, correct: false }, { word_id: 1, correct: false }]));
  });

  it("will not check an empty answer, and locks the answer once checked", async () => {
    installSpeech();
    const { calls } = mockApi(base);
    renderApp("/practice");
    await userEvent.click(await screen.findByRole("button", { name: "Start dictation" }));
    expect(await screen.findByRole("button", { name: "Check" })).toBeDisabled();
    await typeAndCheck("x");
    expect(screen.queryByRole("button", { name: "Check" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Your answer")).toHaveAttribute("readonly");
    expect(answers(calls)).toHaveLength(1);
  });

  it("points to Vocabulary when there are no words to practise", async () => {
    installSpeech();
    mockApi({ ...base, "GET /practice/dictation": { items: [], total: 0 } });
    renderApp("/practice");
    await userEvent.click(await screen.findByRole("button", { name: "Start dictation" }));
    expect(await screen.findByText("No words to practise")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Add words in Vocabulary" })).toHaveAttribute("href", "/vocabulary");
  });

  it("asks only for due words when 'only due' is ticked", async () => {
    installSpeech();
    const { calls } = mockApi(base);
    renderApp("/practice");
    await userEvent.click(await screen.findByLabelText("Only words due for review"));
    await userEvent.click(screen.getByRole("button", { name: "Start dictation" }));
    await screen.findByLabelText("Your answer");
    expect(calls.find((c) => c.path.startsWith("/practice/dictation"))!.path).toContain("due=true");
  });

  it("shows the server's reason when the words cannot be loaded", async () => {
    installSpeech();
    mockApi({ ...base, "GET /practice/dictation": err(500, "internal", "boom") });
    renderApp("/practice");
    await userEvent.click(await screen.findByRole("button", { name: "Start dictation" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
