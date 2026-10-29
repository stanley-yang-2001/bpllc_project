import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ALICE, LANGS, mockApi, renderApp } from "../test/helpers";

afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });

const W = (id: number, word: string, meaning: string | null = null, set_id: number | null = null) => ({ id, language: "en", word, meaning, set_id, created_at: "2026-01-01T00:00:00Z" });
const page = (items: ReturnType<typeof W>[]) => ({ items, total: items.length, limit: 50, offset: 0 });
const SETS = { items: [{ id: 7, name: "Food", language: "en", count: 1 }, { id: 8, name: "Travel", language: "en", count: 0 }], general_count: 2, total_count: 3 };
const OPTIONS = { types: ["narration", "dialogue"], topics: ["a market day"] };
const REPORT = { rules_version: 4, status: "pass", language: { requested: "en", ok: true, verdict: "english" }, structure: { ok: true, leaked_plan: false, units: 4 }, vocabulary: { mode: "strict", ok: true, outside: [], outside_count: 0, limit: 5 }, read_seconds: 6 };
const STORY = { story: "Ana: Hello.\nBen: Hi.", language: "en", story_type: "narration", topic: null, report: REPORT, words_total: 3, words_used: 3 };
const base = { "GET /me": ALICE, "GET /languages": LANGS, "GET /sets": SETS };

describe("vocabulary sets", () => {
  it("shows All, General and each set with counts, and asks the API for the chosen set", async () => {
    const { calls } = mockApi({ ...base, "GET /words": page([W(1, "bread", "pan", 7), W(2, "water")]) });
    renderApp("/vocabulary");
    expect(await screen.findByRole("button", { name: /General/ })).toBeInTheDocument();
    await userEvent.click(await screen.findByRole("button", { name: /Food/ }));
    await waitFor(() => expect(calls.some((c) => c.path.startsWith("/words?") && c.path.includes("set=7"))).toBe(true));
    await userEvent.click(screen.getByRole("button", { name: /General/ }));
    await waitFor(() => expect(calls.some((c) => c.path.startsWith("/words?") && c.path.includes("set=general"))).toBe(true));
  });

  it("creates a set with the name the learner typed", async () => {
    const { calls } = mockApi({ ...base, "GET /words": page([W(1, "bread")]), "POST /sets": { id: 9, name: "Verbs", language: "en", count: 0 } });
    renderApp("/vocabulary");
    await userEvent.type(await screen.findByLabelText("New set name"), "Verbs");
    await userEvent.click(screen.getByRole("button", { name: "Create set" }));
    await waitFor(() => expect(calls.find((c) => c.method === "POST" && c.path === "/sets")!.body).toEqual({ language: "en", name: "Verbs" }));
  });

  it("moves the selected words to a set, and back to General", async () => {
    const { calls } = mockApi({ ...base, "GET /words": page([W(1, "bread", "pan", 7), W(2, "water")]), "POST /words/move": { moved: 2 } });
    renderApp("/vocabulary");
    await userEvent.click(await screen.findByLabelText("Select bread"));
    await userEvent.click(screen.getByLabelText("Select water"));
    await userEvent.selectOptions(screen.getByLabelText("Move selected words to"), "8");
    await waitFor(() => expect(calls.find((c) => c.path === "/words/move")!.body).toEqual({ ids: [1, 2], set_id: 8 }));
    await userEvent.click(await screen.findByLabelText("Select bread"));
    await userEvent.selectOptions(screen.getByLabelText("Move selected words to"), "general");
    await waitFor(() => expect(calls.filter((c) => c.path === "/words/move")[1].body).toEqual({ ids: [1], set_id: null }));
  });

  it("shows the set each word is in", async () => {
    mockApi({ ...base, "GET /words": page([W(1, "bread", "pan", 7)]) });
    renderApp("/vocabulary");
    const row = (await screen.findByText("bread")).closest("tr")!;
    expect(within(row).getByText("Food")).toBeInTheDocument();
  });
});

describe("meanings written by the tutor", () => {
  it("asks again until no word is left without a meaning", async () => {
    const answers = [{ defined: 25, failed: 0, remaining: 5 }, { defined: 5, failed: 0, remaining: 0 }];
    const { calls } = mockApi({ ...base, "GET /words": page([W(1, "bread")]), "POST /words/define": () => ({ json: answers.shift() }) });
    renderApp("/vocabulary");
    await userEvent.click(await screen.findByRole("button", { name: "Write missing meanings" }));
    await waitFor(() => expect(calls.filter((c) => c.path === "/words/define")).toHaveLength(2));
    expect(calls.find((c) => c.path === "/words/define")!.body).toMatchObject({ language: "en", set: "all", meaning_mode: "native" });
    expect(await screen.findByText("Meanings written: 30.")).toBeInTheDocument();
  });

  it("lets the learner choose the language of the meanings, saves it on the account and sends it with the request", async () => {
    const learner = { ...ALICE, native_language: "es", languages: ["en"] };            // Spanish speaker studying English
    const { calls } = mockApi({ ...base, "GET /me": learner, "GET /words": page([W(1, "bread")]),
      "PATCH /me/preferences": { active_language: null, ui_follows_study_language: false, chat_in_study_language: false, meaning_mode: "both", theme: "system", custom_colors: null },
      "POST /words/define": { defined: 1, failed: 0, remaining: 0 } });
    renderApp("/vocabulary");
    const choice = await screen.findByLabelText("Write meanings in");
    expect([...choice.querySelectorAll("option")].map((o) => o.textContent)).toEqual(["My language (Español)", "The language I study (English)", "Both (Español and English)"]);
    await userEvent.selectOptions(choice, "both");
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH" && c.path === "/me/preferences")!.body).toEqual({ meaning_mode: "both" }));
    await userEvent.click(screen.getByRole("button", { name: "Write missing meanings" }));
    await waitFor(() => expect(calls.find((c) => c.path === "/words/define")!.body).toMatchObject({ meaning_mode: "both" }));
  });

  it("does not offer Both when the learner studies their own language", async () => {
    mockApi({ ...base, "GET /words": page([W(1, "bread")]) });                           // native English, studying English
    renderApp("/vocabulary");
    const choice = await screen.findByLabelText("Write meanings in");
    expect([...choice.querySelectorAll("option")].map((o) => o.textContent)).toEqual(["My language (English)", "The language I study (English)"]);
  });

  it("stops when a request writes nothing, instead of asking forever", async () => {
    const { calls } = mockApi({ ...base, "GET /words": page([W(1, "bread")]), "POST /words/define": { defined: 0, failed: 3, remaining: 3 } });
    renderApp("/vocabulary");
    await userEvent.click(await screen.findByRole("button", { name: "Write missing meanings" }));
    await waitFor(() => expect(calls.filter((c) => c.path === "/words/define")).toHaveLength(1));
    await new Promise((r) => setTimeout(r, 100));
    expect(calls.filter((c) => c.path === "/words/define")).toHaveLength(1);
  });

  it("writes the meaning of a new word when the box is ticked, without a meaning typed", async () => {
    const { calls } = mockApi({ ...base, "GET /words": page([]), "POST /words": () => ({ status: 201, json: W(5, "pear") }), "POST /words/define": { defined: 1, failed: 0, remaining: 0 } });
    renderApp("/vocabulary");
    await userEvent.type(await screen.findByLabelText("Word"), "pear");
    await userEvent.click(screen.getByLabelText("Let the tutor write the meaning"));
    await userEvent.click(screen.getByRole("button", { name: "Add word" }));
    await waitFor(() => expect(calls.find((c) => c.path === "/words/define")!.body).toMatchObject({ language: "en", ids: [5] }));
  });

  it("does not ask the tutor when the learner typed a meaning", async () => {
    const { calls } = mockApi({ ...base, "GET /words": page([]), "POST /words": () => ({ status: 201, json: W(5, "pear", "pera") }), "POST /words/define": { defined: 1, failed: 0, remaining: 0 } });
    renderApp("/vocabulary");
    await userEvent.type(await screen.findByLabelText("Word"), "pear");
    await userEvent.type(screen.getByLabelText("Meaning (optional)"), "pera");
    await userEvent.click(screen.getByLabelText("Let the tutor write the meaning"));
    await userEvent.click(screen.getByRole("button", { name: "Add word" }));
    await screen.findByText(/Added|pear/);
    expect(calls.some((c) => c.path === "/words/define")).toBe(false);
  });
});

describe("choosing sets for stories and chat", () => {
  it("Studio sends nothing extra while every set is ticked, and the ticked ids once one is unticked (General is 0)", async () => {
    const { calls } = mockApi({ ...base, "GET /stories/options": OPTIONS, "POST /stories/generate": STORY });
    renderApp("/studio");
    await userEvent.click(await screen.findByRole("button", { name: "Make a story" }));
    await waitFor(() => expect(calls.filter((c) => c.path === "/stories/generate")).toHaveLength(1));
    expect(calls.find((c) => c.path === "/stories/generate")!.body.set_ids).toBeUndefined();
    await userEvent.click(screen.getByLabelText(/^Food/));
    await userEvent.click(screen.getByLabelText(/^Travel/));
    await userEvent.click(screen.getByRole("button", { name: "Make another" }));
    await waitFor(() => expect(calls.filter((c) => c.path === "/stories/generate")).toHaveLength(2));
    expect(calls.filter((c) => c.path === "/stories/generate")[1].body.set_ids).toEqual([0]);
  });

  it("Studio blocks Make while no set is ticked, and General can always be ticked again", async () => {
    mockApi({ ...base, "GET /stories/options": OPTIONS });
    renderApp("/studio");
    const make = await screen.findByRole("button", { name: "Make a story" });
    for (const name of [/^General/, /^Food/, /^Travel/]) await userEvent.click(await screen.findByLabelText(name));
    expect(make).toBeDisabled();
    expect(screen.getByText("Choose at least one set.")).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText(/^General/));
    expect(make).toBeEnabled();
  });

  it("Chat sends the ticked set ids with the message", async () => {
    const { calls } = mockApi({ ...base, "GET /words": page([]), "POST /chat": ({ body }: { body: { session_id: string } }) => ({ json: { reply: "ok", tool_calls: [], session_id: body.session_id } }) });
    renderApp("/chat");
    await userEvent.click(await screen.findByLabelText(/^Travel/));
    await userEvent.type(screen.getByLabelText("Message"), "tell me a story");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByText("ok");
    expect(calls.find((c) => c.path === "/chat")!.body.set_ids).toEqual([0, 7]);
  });

  it("shows no picker for a learner who has made no sets", async () => {
    mockApi({ ...base, "GET /sets": { items: [], general_count: 4, total_count: 4 }, "GET /stories/options": OPTIONS });
    renderApp("/studio");
    await screen.findByRole("button", { name: "Make a story" });
    expect(screen.queryByText("Words to use")).not.toBeInTheDocument();
  });
});

describe("multiple choice practice", () => {
  const CH = { items: [
    { id: 1, prompt: "water", answer: "a drink", choices: ["a drink", "baked food", "a home", "a color"], direction: "meaning" },
    { id: 2, prompt: "bread", answer: "baked food", choices: ["a drink", "baked food", "a home", "a color"], direction: "meaning" },
  ], total: 5 };

  it("asks the API for the chosen direction and set, then marks right and wrong answers and scores", async () => {
    const { calls } = mockApi({ ...base, "GET /stories": { items: [], total: 0, limit: 100, offset: 0 }, "GET /practice/choices": CH });
    renderApp("/practice");
    await userEvent.selectOptions(await screen.findByLabelText("Words from"), "7");
    await userEvent.click(screen.getByRole("button", { name: "Start multiple choice" }));
    await userEvent.click(await screen.findByRole("button", { name: "a drink" }));
    expect(screen.getByText("Correct!")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await userEvent.click(await screen.findByRole("button", { name: "a color" }));
    expect(screen.getByText("Not quite. The answer is: baked food")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "See result" }));
    expect(await screen.findByText("You got 1 of 2.")).toBeInTheDocument();
    expect(calls.find((c) => c.path.startsWith("/practice/choices"))!.path).toBe("/practice/choices?language=en&limit=10&direction=meaning&set=7");
  });

  it("can ask for the word given the meaning", async () => {
    const { calls } = mockApi({ ...base, "GET /stories": { items: [], total: 0, limit: 100, offset: 0 }, "GET /practice/choices": { items: [], total: 1 } });
    renderApp("/practice");
    await userEvent.selectOptions(await screen.findByLabelText("Question"), "word");
    await userEvent.click(screen.getByRole("button", { name: "Start multiple choice" }));
    expect(await screen.findByText("Not enough words with meanings")).toBeInTheDocument();
    expect(calls.find((c) => c.path.startsWith("/practice/choices"))!.path).toContain("direction=word");
  });
});
