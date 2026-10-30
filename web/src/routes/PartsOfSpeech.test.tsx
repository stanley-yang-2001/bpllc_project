import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ALICE, err, LANGS, mockApi, renderApp } from "../test/helpers";

afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });

const EN = ["noun", "verb", "adjective", "adverb", "pronoun", "determiner", "preposition", "conjunction", "interjection", "phrase"];
const W = (id: number, word: string, pos: string | null = null) => ({ id, language: "en", word, meaning: null, pos, created_at: "2026-01-01T00:00:00Z" });
const page = (items: ReturnType<typeof W>[]) => ({ items, total: items.length, limit: 50, offset: 0 });
const base = { "GET /me": ALICE, "GET /languages": LANGS, "GET /words/parts-of-speech": { language: "en", items: EN }, "GET /sets": { items: [] },
  "GET /words/starter-packs": { items: [], gloss_available: true }, "GET /stories": { items: [], total: 0, limit: 100, offset: 0 } };

describe("part of speech on the vocabulary page", () => {
  it("shows a column with each word's label, in words", async () => {
    mockApi({ ...base, "GET /words": page([W(1, "run", "verb"), W(2, "table")]) });
    renderApp("/vocabulary");
    expect(await screen.findByRole("columnheader", { name: "Part of speech" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Part of speech of run")).toHaveValue("verb"));
    expect(screen.getByLabelText("Part of speech of table")).toHaveValue("");
  });

  it("offers the language's own categories and saves a choice, or clears it", async () => {
    const { calls } = mockApi({ ...base, "GET /words": page([W(1, "table")]), "PATCH /words/1": W(1, "table", "noun") });
    renderApp("/vocabulary");
    const select = await screen.findByLabelText("Part of speech of table");
    await waitFor(() => expect(within(select).getAllByRole("option")).toHaveLength(EN.length + 1));
    await userEvent.selectOptions(select, "noun");
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH")!.body).toEqual({ pos: "noun" }));
  });

  it("the Label button asks the tutor until nothing is left, and says how many", async () => {
    const answers = [{ defined: 25, failed: 0, remaining: 3 }, { defined: 3, failed: 0, remaining: 0 }];
    const { calls } = mockApi({ ...base, "GET /words": page([W(1, "run")]), "POST /words/label": () => ({ json: answers.shift() }) });
    renderApp("/vocabulary");
    await userEvent.click(await screen.findByRole("button", { name: "Label parts of speech" }));
    expect(await screen.findByText("The tutor labelled 28 words.")).toBeInTheDocument();
    expect(calls.filter((c) => c.path === "/words/label")).toHaveLength(2);
  });

  it("says so when nothing could be labelled, and shows the server's reason on failure", async () => {
    mockApi({ ...base, "GET /words": page([W(1, "run")]), "POST /words/label": { defined: 0, failed: 0, remaining: 0 } });
    const { ui } = renderApp("/vocabulary");
    await userEvent.click(await screen.findByRole("button", { name: "Label parts of speech" }));
    expect(await screen.findByText(/already has a label/)).toBeInTheDocument();
    ui.unmount();
    mockApi({ ...base, "GET /words": page([W(1, "run")]), "POST /words/label": err(502, "ai_failed", "The tutor couldn't label the words. Please try again in a moment.") });
    renderApp("/vocabulary");
    await userEvent.click(await screen.findByRole("button", { name: "Label parts of speech" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("couldn't label the words");
  });

  it("a new word can be added with a label chosen, or with the tutor asked to label it", async () => {
    const { calls } = mockApi({ ...base, "GET /words": page([]), "POST /words": W(5, "run", "verb"), "POST /words/label": { defined: 1, failed: 0, remaining: 0 } });
    renderApp("/vocabulary");
    await userEvent.type(await screen.findByLabelText("Word", { exact: true }), "run");
    await userEvent.selectOptions(screen.getByLabelText("Part of speech (optional)"), "verb");
    await userEvent.click(screen.getByRole("button", { name: "Add word" }));
    await waitFor(() => expect(calls.find((c) => c.method === "POST" && c.path === "/words")!.body).toMatchObject({ word: "run", pos: "verb" }));
    expect(calls.some((c) => c.path === "/words/label")).toBe(false);
    await userEvent.type(screen.getByLabelText("Word", { exact: true }), "walk");
    await userEvent.click(screen.getByLabelText("Let the tutor label the part of speech"));
    await userEvent.click(screen.getByRole("button", { name: "Add word" }));
    await waitFor(() => expect(calls.find((c) => c.path === "/words/label")!.body).toMatchObject({ language: "en", ids: [5] }));
  });
});

describe("parts-of-speech practice", () => {
  const CARDS = { items: [{ id: 1, word: "run", answer: "verb", options: EN, meaning: "to move fast" }, { id: 2, word: "red", answer: "adjective", options: EN, meaning: null }], total: 2 };

  it("shows the word, the language's categories, and marks right and wrong answers, recording each", async () => {
    const { calls } = mockApi({ ...base, "GET /practice/pos": CARDS, "POST /practice/answers": { status: 204 } });
    renderApp("/practice");
    await userEvent.click(await screen.findByRole("button", { name: "Start parts of speech" }));
    expect(await screen.findByText("run")).toBeInTheDocument();
    expect(calls.find((c) => c.path.startsWith("/practice/pos"))!.path).toBe("/practice/pos?language=en&limit=10");
    const group = screen.getByRole("group", { name: "Choices" });
    expect(within(group).getAllByRole("button")).toHaveLength(EN.length);
    await userEvent.click(within(group).getByRole("button", { name: "verb" }));
    expect(screen.getByText("Correct!")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await userEvent.click(await within(screen.getByRole("group", { name: "Choices" })).findByRole("button", { name: "noun" }));
    expect(screen.getByText("Not quite. It is: adjective")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "See result" }));
    expect(await screen.findByText("You got 1 of 2.")).toBeInTheDocument();
    await waitFor(() => expect(calls.filter((c) => c.path === "/practice/answers").map((c) => c.body.answers[0])).toEqual([{ word_id: 1, correct: true }, { word_id: 2, correct: false }]));
  });

  it("points to Vocabulary when no word has a label", async () => {
    mockApi({ ...base, "GET /practice/pos": { items: [], total: 0 } });
    renderApp("/practice");
    await userEvent.click(await screen.findByRole("button", { name: "Start parts of speech" }));
    expect(await screen.findByText("No labelled words yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Label words in Vocabulary" })).toHaveAttribute("href", "/vocabulary");
  });

  it("asks only for due words when 'only due' is ticked", async () => {
    const { calls } = mockApi({ ...base, "GET /practice/pos": CARDS });
    renderApp("/practice");
    await userEvent.click(await screen.findByLabelText("Only words due for review"));
    await userEvent.click(screen.getByRole("button", { name: "Start parts of speech" }));
    await screen.findByText("run");
    expect(calls.find((c) => c.path.startsWith("/practice/pos"))!.path).toContain("due=true");
  });
});
