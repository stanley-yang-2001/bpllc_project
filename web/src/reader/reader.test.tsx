import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAuth } from "../auth/AuthContext";
import { ToastProvider } from "../components/Toast";
import { ALICE, err, LANGS, mockApi, renderIn } from "../test/helpers";
import { GlossedText } from "./GlossedText";

afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });

const TEXT = "The dogs were running.";
const base = { "GET /me": ALICE, "GET /languages": LANGS };
const GLOSS = {
  spans: [{ start: 4, end: 8, word_id: 1 }, { start: 14, end: 21, word_id: 2 }],
  words: [{ id: 1, word: "dog", meaning: "a pet", pos: null }, { id: 2, word: "run", meaning: null, pos: null }],
};
const AFTER_ADDING_WERE = {
  spans: [GLOSS.spans[0], { start: 9, end: 13, word_id: 3 }, GLOSS.spans[1]],
  words: [...GLOSS.words, { id: 3, word: "were", meaning: "the past of be", pos: null }],
};
const NEW_WORD = (word: string) => ({ id: 3, language: "en", word, meaning: null, set_id: null, created_at: "2026-01-01T00:00:00Z" });
/** The app draws its pages only for a signed-in learner; here the story waits for the mocked GET /me the same way. */
function SignedIn({ children }: { children: React.ReactNode }) { return useAuth().user ? <>{children}</> : null; }
function Harness({ first }: { first: string }) {
  const [text, setText] = useState(first);
  return <ToastProvider><SignedIn><GlossedText text={text} language="en" /><button type="button" onClick={() => setText("Another story.")}>Change the text</button></SignedIn></ToastProvider>;
}
const show = (text = TEXT) => renderIn(<Harness first={text} />);
const card = () => screen.queryByRole("region", { name: "About this word" });
const to = (calls: ReturnType<typeof mockApi>["calls"], path: string) => calls.filter((c) => c.method === "POST" && c.path === path);

describe("the reader", () => {
  it("underlines the learner's words as buttons, and the text still reads the same", async () => {
    const { calls } = mockApi({ ...base, "POST /reading/gloss": GLOSS });
    const { ui } = show();
    expect(await screen.findByRole("button", { name: "dogs" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "running" })).toBeInTheDocument();
    expect(ui.container.querySelector("p")!.textContent).toBe(TEXT);
    expect(to(calls, "/reading/gloss")).toHaveLength(1);
    expect(to(calls, "/reading/gloss")[0].body).toEqual({ language: "en", text: TEXT });
    expect(screen.getByText(/Your words are underlined/)).toBeInTheDocument();
  });

  it("shows the story as plain text until the API has answered, and keeps it plain when the API fails", async () => {
    let release: () => void = () => undefined;
    const held = new Promise<void>((r) => { release = r; });
    mockApi({ ...base, "POST /reading/gloss": () => ({ json: GLOSS, after: held }) });
    show();
    expect(await screen.findByText(TEXT)).toBeInTheDocument();             // one piece of text, no buttons yet
    expect(screen.queryByRole("button", { name: "dogs" })).not.toBeInTheDocument();
    release();
    expect(await screen.findByRole("button", { name: "dogs" })).toBeInTheDocument();
  });

  it("leaves the story plain when the API fails", async () => {
    const { calls } = mockApi({ ...base, "POST /reading/gloss": err(500, "server_error", "boom") });
    show();
    expect(await screen.findByText(TEXT)).toBeInTheDocument();
    await waitFor(() => expect(to(calls, "/reading/gloss")).toHaveLength(1));
    await new Promise((r) => setTimeout(r, 30));
    expect(screen.getByText(TEXT)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "dogs" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Your words are underlined/)).not.toBeInTheDocument();
  });

  it("opens a card with the saved meaning when an underlined word is tapped, and closes it by the word, the Close button or Escape", async () => {
    mockApi({ ...base, "POST /reading/gloss": GLOSS });
    show();
    const word = await screen.findByRole("button", { name: "dogs" });
    await userEvent.click(word);
    expect(word).toHaveAttribute("aria-pressed", "true");
    const c = within(card()!);
    expect(c.getByText("dog")).toBeInTheDocument();                       // the word as in the list
    expect(c.getByText("a pet")).toBeInTheDocument();
    await userEvent.click(word);
    expect(card()).not.toBeInTheDocument();
    await userEvent.click(word);
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(card()).not.toBeInTheDocument();
    await userEvent.click(word);
    await userEvent.keyboard("{Escape}");
    expect(card()).not.toBeInTheDocument();
  });

  it("offers to have the tutor write a meaning that is missing, and refreshes the text after", async () => {
    let defined = false;
    const filled = { ...GLOSS, words: [GLOSS.words[0], { id: 2, word: "run", meaning: "to move fast", pos: null }] };
    const { calls } = mockApi({ ...base, "POST /reading/gloss": () => ({ json: defined ? filled : GLOSS }),
      "POST /words/define": () => { defined = true; return { json: { defined: 1, failed: 0, remaining: 0 } }; } });
    show();
    await userEvent.click(await screen.findByRole("button", { name: "running" }));
    expect(screen.getByText("No meaning saved yet.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Let the tutor write the meaning" }));
    expect(await screen.findByText("to move fast")).toBeInTheDocument();
    expect(to(calls, "/words/define")[0].body).toMatchObject({ ids: [2], language: "en" });
  });

  it("lets a word that is not in the list be added, with a meaning from the tutor, and then shows it as one of the learner's words", async () => {
    let added = false;
    const { calls } = mockApi({ ...base,
      "POST /reading/gloss": () => ({ json: added ? AFTER_ADDING_WERE : GLOSS }),
      "POST /words": () => { added = true; return { status: 201, json: NEW_WORD("were") }; },
      "POST /words/define": { defined: 1, failed: 0, remaining: 0 } });
    show();
    await screen.findByRole("button", { name: "dogs" });
    await userEvent.click(screen.getByText("were"));
    expect(screen.getByText("“were” is not in your words yet.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Add word" }));
    expect(await screen.findByText("the past of be")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add word" })).not.toBeInTheDocument();
    expect(to(calls, "/words")[0].body).toEqual({ language: "en", word: "were" });
    expect(to(calls, "/words/define")[0].body).toMatchObject({ ids: [3], language: "en" });
    expect(await screen.findByRole("button", { name: "were" })).toBeInTheDocument();       // underlined now
  });

  it("adds without asking the tutor when the box is cleared, and adds a sentence-initial word in lower case", async () => {
    const { calls } = mockApi({ ...base, "POST /reading/gloss": GLOSS, "POST /words": { status: 201, json: NEW_WORD("the") } });
    show();
    await screen.findByRole("button", { name: "dogs" });
    await userEvent.click(screen.getByText("The"));
    await userEvent.click(screen.getByRole("checkbox", { name: "Let the tutor write the meaning" }));
    await userEvent.click(screen.getByRole("button", { name: "Add word" }));
    await waitFor(() => expect(to(calls, "/words")).toHaveLength(1));
    expect(to(calls, "/words")[0].body).toEqual({ language: "en", word: "the" });
    expect(to(calls, "/words/define")).toHaveLength(0);
  });

  it("says why a word could not be added and keeps the card open", async () => {
    mockApi({ ...base, "POST /reading/gloss": GLOSS, "POST /words": err(409, "duplicate_word", "That word is already in your list.") });
    show();
    await screen.findByRole("button", { name: "dogs" });
    await userEvent.click(screen.getByText("were"));
    await userEvent.click(screen.getByRole("button", { name: "Add word" }));
    expect(await screen.findByText("That word is already in your list.")).toBeInTheDocument();
    expect(card()).toBeInTheDocument();
  });

  it("closes the card when the text changes", async () => {
    mockApi({ ...base, "POST /reading/gloss": GLOSS });
    show();
    await userEvent.click(await screen.findByRole("button", { name: "dogs" }));
    expect(card()).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Change the text" }));
    await waitFor(() => expect(card()).not.toBeInTheDocument());
  });
});
