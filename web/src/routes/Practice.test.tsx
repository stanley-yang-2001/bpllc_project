import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ALICE, err, LANGS, mockApi, renderApp } from "../test/helpers";

afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });

const CARDS = { items: [{ id: 1, word: "water", meaning: "a drink" }, { id: 2, word: "bread", meaning: "baked food" }, { id: 3, word: "house", meaning: "a home" }], total: 3 };
const item = (answer: string, over: Record<string, unknown> = {}) => ({ before: "Ana: I want ", after: " please.", answer, hint: "a drink", choices: [answer, "bread", "house"], word_id: null, ...over });
const CLOZE = { story_id: 5, language: "en", items: [item("water"), item("bread", { before: "Ben: Here is some ", after: ".", hint: "baked food", choices: ["water", "bread", "house"] })] };
const STORIES = { items: [{ id: 5, language: "en", story_type: "dialogue", topic: null, body: "Ana: Hello.\nBen: Hi.", passed: true, created_at: "2026-10-16T10:00:00Z" }], total: 1, limit: 100, offset: 0 };
const base = { "GET /me": ALICE, "GET /languages": LANGS, "GET /stories": STORIES };

describe("practice page", () => {
  it("offers flashcards and fill-in-the-blank, and says practice costs nothing", async () => {
    mockApi(base);
    renderApp("/practice");
    expect(await screen.findByRole("button", { name: "Start flashcards" })).toBeInTheDocument();
    expect(await screen.findByLabelText("Story")).toBeInTheDocument();
    expect(screen.getByText(/costs nothing from the shared limit/)).toBeInTheDocument();
  });

  it("asks for ten flashcards in the active language and shows the word, then the meaning", async () => {
    const { calls } = mockApi({ ...base, "GET /practice/flashcards": CARDS });
    renderApp("/practice");
    await userEvent.click(await screen.findByRole("button", { name: "Start flashcards" }));
    expect(await screen.findByText("water")).toBeInTheDocument();
    expect(screen.queryByText("a drink")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show meaning" }));
    expect(screen.getByText("a drink")).toBeInTheDocument();
    expect(calls.find((c) => c.path.startsWith("/practice/flashcards"))!.path).toBe("/practice/flashcards?language=en&limit=10");
  });

  it("counts the cards the learner knew and offers another round with a fresh request", async () => {
    const { calls } = mockApi({ ...base, "GET /practice/flashcards": CARDS });
    renderApp("/practice");
    await userEvent.click(await screen.findByRole("button", { name: "Start flashcards" }));
    for (const knew of [true, false, true]) {
      await userEvent.click(await screen.findByRole("button", { name: "Show meaning" }));
      await userEvent.click(screen.getByRole("button", { name: knew ? "I knew it" : "Not yet" }));
    }
    expect(await screen.findByText("You knew 2 of 3")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Practise again" }));
    expect(await screen.findByText("Card 1 of 3")).toBeInTheDocument();
    await waitFor(() => expect(calls.filter((c) => c.path.startsWith("/practice/flashcards"))).toHaveLength(2));
  });

  it("says what to do when no word has a meaning", async () => {
    mockApi({ ...base, "GET /practice/flashcards": { items: [], total: 0 } });
    renderApp("/practice");
    await userEvent.click(await screen.findByRole("button", { name: "Start flashcards" }));
    expect(await screen.findByText("No flashcards yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Add meanings in Vocabulary" })).toHaveAttribute("href", "/vocabulary");
  });

  it("opens fill-in-the-blank for the story picked, and for a story named in the address", async () => {
    const { calls } = mockApi({ ...base, "GET /practice/cloze": CLOZE });
    renderApp("/practice?story=5");
    expect(await screen.findByText("Sentence 1 of 2")).toBeInTheDocument();
    expect(calls.find((c) => c.path.startsWith("/practice/cloze"))!.path).toBe("/practice/cloze?story_id=5");
  });

  it("picking a story in the list starts it", async () => {
    mockApi({ ...base, "GET /practice/cloze": CLOZE });
    renderApp("/practice");
    await userEvent.selectOptions(await screen.findByLabelText("Story"), "5");
    expect(await screen.findByText("Sentence 1 of 2")).toBeInTheDocument();
  });

  it("marks a right answer, reveals the answer after a wrong one, and totals the score", async () => {
    mockApi({ ...base, "GET /practice/cloze": CLOZE });
    renderApp("/practice?story=5");
    await userEvent.click(await screen.findByRole("button", { name: "water" }));
    expect(screen.getByText("Correct!")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await userEvent.click(await screen.findByRole("button", { name: "house" }));
    expect(screen.getByText("Not quite. The answer is “bread”.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "See result" }));
    expect(await screen.findByText("You got 1 of 2")).toBeInTheDocument();
  });

  it("locks the choice once answered, so a second click cannot change the score", async () => {
    mockApi({ ...base, "GET /practice/cloze": CLOZE });
    renderApp("/practice?story=5");
    await userEvent.click(await screen.findByRole("button", { name: "house" }));
    await userEvent.click(screen.getByRole("button", { name: "water" }));          // the answer stays clickable but must not score
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await userEvent.click(await screen.findByRole("button", { name: "bread" }));
    await userEvent.click(screen.getByRole("button", { name: "See result" }));
    expect(await screen.findByText("You got 1 of 2")).toBeInTheDocument();
  });

  it("shows the server's reason when a story has nothing to practise", async () => {
    mockApi({ ...base, "GET /practice/cloze": err(422, "no_blanks", "This story has no words from your list to practise. Try another story.") });
    renderApp("/practice?story=5");
    expect(await screen.findByRole("alert")).toHaveTextContent("This story has no words from your list");
  });

  it("ignores an address that is not a story number", async () => {
    const { calls } = mockApi(base);
    renderApp("/practice?story=abc");
    expect(await screen.findByRole("button", { name: "Start flashcards" })).toBeInTheDocument();
    expect(calls.some((c) => c.path.startsWith("/practice/cloze"))).toBe(false);
  });

  it("points to Story Studio when there are no saved stories", async () => {
    mockApi({ ...base, "GET /stories": { items: [], total: 0, limit: 100, offset: 0 } });
    renderApp("/practice");
    expect(await screen.findByRole("link", { name: "Make one in Story Studio" })).toHaveAttribute("href", "/studio");
  });

  it("Back from a finished round returns to the two choices", async () => {
    mockApi({ ...base, "GET /practice/cloze": { ...CLOZE, items: [CLOZE.items[0]] } });
    renderApp("/practice?story=5");
    await userEvent.click(await screen.findByRole("button", { name: "water" }));
    await userEvent.click(screen.getByRole("button", { name: "See result" }));
    await userEvent.click(await screen.findByRole("button", { name: "Back" }));
    expect(await screen.findByRole("button", { name: "Start flashcards" })).toBeInTheDocument();
  });

  it("keeps the answer out of the sentence until the learner has chosen, and shows the hint", async () => {
    mockApi({ ...base, "GET /practice/cloze": CLOZE });
    renderApp("/practice?story=5");
    const sentence = await screen.findByText(/Ana: I want/);
    expect(sentence).not.toHaveTextContent("water");
    expect(screen.getByText("Hint: a drink")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "house" }));
    expect(sentence).toHaveTextContent("water");
  });

  it("ignores story numbers that are zero, negative or fractions", async () => {
    for (const bad of ["0", "-3", "2.5"]) {
      const { calls } = mockApi(base);
      const { ui } = renderApp(`/practice?story=${bad}`);
      expect(await screen.findByRole("button", { name: "Start flashcards" })).toBeInTheDocument();
      expect(calls.some((c) => c.path.startsWith("/practice/cloze")), bad).toBe(false);
      ui.unmount();
    }
  });

  it("leaves a flashcard round when the language changes", async () => {
    mockApi({ ...base, "GET /me": { ...ALICE, languages: ["en", "es"] }, "GET /practice/flashcards": CARDS });
    renderApp("/practice");
    await userEvent.click(await screen.findByRole("button", { name: "Start flashcards" }));
    await screen.findByText("Card 1 of 3");
    await userEvent.selectOptions(screen.getByLabelText("Active language"), "es");
    expect(await screen.findByRole("button", { name: "Start flashcards" })).toBeInTheDocument();
  });
  describe("remembered results and review", () => {
    const PROGRESS = { language: "en", new: 2, learning: 1, known: 3, due: 4, streak: 5, practised_today: true };
    const ANSWERS = (calls: { method: string; path: string; body: any }[]) => calls.filter((c) => c.method === "POST" && c.path === "/practice/answers").map((c) => c.body.answers[0]);

    it("shows what is due, new, learning and known, and the streak", async () => {
      mockApi({ ...base, "GET /practice/progress": PROGRESS });
      renderApp("/practice");
      expect(await screen.findByText("Your progress")).toBeInTheDocument();
      for (const [label, n] of [["Due now", "4"], ["New", "2"], ["Learning", "1"], ["Known", "3"]]) expect(screen.getByText(label).nextElementSibling).toHaveTextContent(n);
      expect(screen.getByText("5-day streak")).toBeInTheDocument();
    });

    it("hides the progress card when no word has a meaning yet, and when it cannot be loaded", async () => {
      mockApi({ ...base, "GET /practice/progress": { ...PROGRESS, new: 0, learning: 0, known: 0, due: 0, streak: 0 } });
      const { ui } = renderApp("/practice");
      expect(await screen.findByRole("button", { name: "Start flashcards" })).toBeInTheDocument();
      expect(screen.queryByText("Your progress")).not.toBeInTheDocument();
      ui.unmount();
      mockApi({ ...base, "GET /practice/progress": err(500, "internal", "boom") });
      renderApp("/practice");
      expect(await screen.findByRole("button", { name: "Start flashcards" })).toBeInTheDocument();
      expect(screen.queryByText("Your progress")).not.toBeInTheDocument();
    });

    it("Review due words starts flashcards for the due words only", async () => {
      const { calls } = mockApi({ ...base, "GET /practice/progress": PROGRESS, "GET /practice/flashcards": CARDS });
      renderApp("/practice");
      await userEvent.click(await screen.findByRole("button", { name: "Review due words" }));
      expect(await screen.findByText("water")).toBeInTheDocument();
      expect(calls.find((c) => c.path.startsWith("/practice/flashcards"))!.path).toBe("/practice/flashcards?language=en&limit=10&due=true");
    });

    it("says nothing is due instead of offering a review button", async () => {
      mockApi({ ...base, "GET /practice/progress": { ...PROGRESS, due: 0, new: 0 } });
      renderApp("/practice");
      expect(await screen.findByText(/Nothing is due right now/)).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Review due words" })).not.toBeInTheDocument();
    });

    it("the 'only due words' box applies to multiple choice too", async () => {
      const choices = { items: [{ id: 7, prompt: "water", answer: "a drink", choices: ["a drink", "x", "y", "z"], direction: "meaning" }], total: 1 };
      const { calls } = mockApi({ ...base, "GET /practice/progress": PROGRESS, "GET /practice/choices": choices });
      renderApp("/practice");
      await userEvent.click(await screen.findByLabelText("Only words due for review"));
      await userEvent.click(screen.getByRole("button", { name: "Start multiple choice" }));
      await screen.findByText("water");
      expect(calls.find((c) => c.path.startsWith("/practice/choices"))!.path).toContain("due=true");
    });

    it("explains an empty due round and goes back", async () => {
      mockApi({ ...base, "GET /practice/progress": PROGRESS, "GET /practice/flashcards": { items: [], total: 0 } });
      renderApp("/practice");
      await userEvent.click(await screen.findByRole("button", { name: "Review due words" }));
      expect(await screen.findByText("Nothing due right now")).toBeInTheDocument();
      await userEvent.click(screen.getByRole("button", { name: "Back" }));
      expect(await screen.findByRole("button", { name: "Start flashcards" })).toBeInTheDocument();
    });

    it("records each flashcard answer as it is given", async () => {
      const { calls } = mockApi({ ...base, "GET /practice/flashcards": CARDS, "POST /practice/answers": { status: 204 } });
      renderApp("/practice");
      await userEvent.click(await screen.findByRole("button", { name: "Start flashcards" }));
      for (const knew of [true, false]) {
        await userEvent.click(await screen.findByRole("button", { name: "Show meaning" }));
        await userEvent.click(screen.getByRole("button", { name: knew ? "I knew it" : "Not yet" }));
      }
      await waitFor(() => expect(ANSWERS(calls)).toEqual([{ word_id: 1, correct: true }, { word_id: 2, correct: false }]));
    });

    it("records multiple-choice answers once each, even if the learner clicks again", async () => {
      const choices = { items: [{ id: 7, prompt: "water", answer: "a drink", choices: ["a drink", "x", "y", "z"], direction: "meaning" }], total: 1 };
      const { calls } = mockApi({ ...base, "GET /practice/choices": choices, "POST /practice/answers": { status: 204 } });
      renderApp("/practice");
      await userEvent.click(await screen.findByRole("button", { name: "Start multiple choice" }));
      await userEvent.click(await screen.findByRole("button", { name: "x" }));
      await userEvent.click(screen.getByRole("button", { name: "a drink" }));
      await waitFor(() => expect(ANSWERS(calls)).toEqual([{ word_id: 7, correct: false }]));
    });

    it("records fill-in-the-blank answers against the word, and skips a blank with no word", async () => {
      const cloze = { ...CLOZE, items: [item("water", { word_id: 3 }), item("bread", { word_id: null, choices: ["water", "bread", "house"] })] };
      const { calls } = mockApi({ ...base, "GET /practice/cloze": cloze, "POST /practice/answers": { status: 204 } });
      renderApp("/practice?story=5");
      await userEvent.click(await screen.findByRole("button", { name: "water" }));
      await userEvent.click(screen.getByRole("button", { name: "Next" }));
      await userEvent.click(await screen.findByRole("button", { name: "bread" }));
      await waitFor(() => expect(ANSWERS(calls)).toEqual([{ word_id: 3, correct: true }]));
    });

    it("tells the learner on the result screen when answers could not be saved", async () => {
      mockApi({ ...base, "GET /practice/flashcards": { items: [CARDS.items[0]], total: 1 }, "POST /practice/answers": err(500, "internal", "boom") });
      renderApp("/practice");
      await userEvent.click(await screen.findByRole("button", { name: "Start flashcards" }));
      await userEvent.click(await screen.findByRole("button", { name: "Show meaning" }));
      await userEvent.click(screen.getByRole("button", { name: "I knew it" }));
      expect(await screen.findByText("You knew 1 of 1")).toBeInTheDocument();
      expect(await screen.findByText(/couldn't be saved this time/)).toBeInTheDocument();
    });
  });
});
