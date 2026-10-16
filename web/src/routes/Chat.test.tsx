import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { wordsKey } from "../api/keys";
import { SLOW_AFTER_MS } from "../chat/ChatContext";
import { ALICE, BOB, err, LANGS, mockApi, renderApp } from "../test/helpers";

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });

const base = { "GET /me": ALICE, "GET /languages": LANGS, "GET /words": { items: [], total: 0, limit: 50, offset: 0 } };
const tool = (name: string, args: Record<string, unknown>, output: string, failed = false) => ({ name, args, output, failed });
const reply = (text: string, tool_calls: ReturnType<typeof tool>[] = []) =>
  ({ body }: { body: { session_id: string } }) => ({ json: { reply: text, tool_calls, session_id: body.session_id } });
const chatCalls = (calls: ReturnType<typeof mockApi>["calls"]) => calls.filter((c) => c.method === "POST" && c.path === "/chat");

async function say(text: string) {
  await userEvent.type(await screen.findByLabelText("Message"), text);
  await userEvent.click(screen.getByRole("button", { name: "Send" }));
}

describe("chat page", () => {
  it("starts with an empty state that says what the tutor can do", async () => {
    mockApi(base);
    renderApp("/chat");
    expect(await screen.findByText(/add a word to your vocabulary/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("sends the message with the active language and a 32-character session id, and shows the reply", async () => {
    const { calls } = mockApi({ ...base, "POST /chat": reply("Hola! ¿Cómo estás?") });
    renderApp("/chat");
    await say("hello");
    expect(await screen.findByText("Hola! ¿Cómo estás?")).toBeInTheDocument();
    expect(screen.getByText("hello")).toBeInTheDocument();
    const call = chatCalls(calls)[0];
    expect(call.body).toEqual({ message: "hello", language: "en", session_id: expect.stringMatching(/^[0-9a-f]{32}$/) });
    expect(call.headers["X-Expected-User"]).toBe("1");
    expect(call.headers["X-Requested-With"]).toBe("tutor");
    expect(screen.getByLabelText("Message")).toHaveValue("");
  });

  it("keeps the same session id for the whole conversation", async () => {
    const { calls } = mockApi({ ...base, "POST /chat": reply("ok") });
    renderApp("/chat");
    await say("one");
    await screen.findAllByText("ok");
    await say("two");
    await waitFor(() => expect(chatCalls(calls)).toHaveLength(2));
    const [a, b] = chatCalls(calls).map((c) => c.body.session_id);
    expect(a).toBe(b);
  });

  it("Enter sends and Shift+Enter makes a new line", async () => {
    const { calls } = mockApi({ ...base, "POST /chat": reply("ok") });
    renderApp("/chat");
    const box = await screen.findByLabelText("Message");
    await userEvent.type(box, "line one{Shift>}{Enter}{/Shift}line two");
    expect(chatCalls(calls)).toHaveLength(0);
    expect(box).toHaveValue("line one\nline two");
    await userEvent.type(box, "{Enter}");
    await waitFor(() => expect(chatCalls(calls)).toHaveLength(1));
    expect(chatCalls(calls)[0].body.message).toBe("line one\nline two");
  });

  it("does not send on Enter while an input method is composing (Japanese, Chinese, Korean)", async () => {
    const { calls } = mockApi({ ...base, "POST /chat": reply("ok") });
    renderApp("/chat");
    const box = await screen.findByLabelText("Message");
    await userEvent.type(box, "にほん");
    const { fireEvent } = await import("@testing-library/react");
    fireEvent.keyDown(box, { key: "Enter", isComposing: true });
    expect(chatCalls(calls)).toHaveLength(0);
  });

  it("will not send an empty or whitespace-only message", async () => {
    const { calls } = mockApi({ ...base, "POST /chat": reply("ok") });
    renderApp("/chat");
    await userEvent.type(await screen.findByLabelText("Message"), "   ");
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Message"), "{Enter}");
    expect(chatCalls(calls)).toHaveLength(0);
  });

  it("limits the message length in the box", async () => {
    mockApi(base);
    renderApp("/chat");
    expect(await screen.findByLabelText("Message")).toHaveAttribute("maxLength", "2000");
  });

  it("does not keep the conversation anywhere on the device", async () => {
    mockApi({ ...base, "POST /chat": reply("a private answer") });
    renderApp("/chat");
    await say("a private question");
    await screen.findByText("a private answer");
    const stored = JSON.stringify({ ...localStorage }) + JSON.stringify({ ...sessionStorage });
    expect(stored).not.toContain("private");
  });
});

describe("tool trace", () => {
  it("shows which tool the tutor used, with its arguments and output, collapsed until opened", async () => {
    mockApi({ ...base, "POST /chat": reply("Added 'bread' to your English vocabulary.", [tool("Add Word", { word: "bread" }, "Added 'bread' to your English vocabulary.")]) });
    renderApp("/chat");
    await say("add the word bread");
    const summary = await screen.findByText("Used Add Word");
    const details = summary.closest("details")!;
    expect(details).not.toHaveAttribute("open");
    await userEvent.click(summary);
    expect(details).toHaveAttribute("open");
    expect(details).toHaveTextContent("bread");
  });

  it("marks a tool that did not work", async () => {
    mockApi({ ...base, "POST /chat": reply("Couldn't add word: too long", [tool("Add Word", { word: "x" }, "Couldn't add word: too long", true)]) });
    renderApp("/chat");
    await say("add the word x");
    expect(await screen.findByText("Add Word didn't work")).toBeInTheDocument();
  });

  it("shows no trace for a plain reply", async () => {
    mockApi({ ...base, "POST /chat": reply("Hello!") });
    renderApp("/chat");
    await say("hi");
    await screen.findByText("Hello!");
    expect(screen.queryByText(/^Used /)).not.toBeInTheDocument();
  });
});

describe("words added through chat", () => {
  const key = wordsKey(1, "en", "", 0);
  const stale = { items: [], total: 0, limit: 50, offset: 0 };

  it("makes the vocabulary list and the language list refresh", async () => {
    const { calls } = mockApi({ ...base, "POST /chat": reply("Added.", [tool("Add Word", { word: "bread" }, "Added.")]) });
    const { client } = renderApp("/chat");
    client.setQueryData(key, stale);
    await say("add the word bread");
    await screen.findByText("Added.", { selector: "p" });
    await waitFor(() => expect(client.getQueryState(key)?.isInvalidated).toBe(true));
    await waitFor(() => expect(calls.filter((c) => c.path === "/me").length).toBeGreaterThan(1));
  });

  it("does not refresh anything when the word was not added", async () => {
    mockApi({ ...base, "POST /chat": reply("Couldn't add word.", [tool("Add Word", { word: "x" }, "Couldn't add word.", true)]) });
    const { client } = renderApp("/chat");
    client.setQueryData(key, stale);
    await say("add the word x");
    await screen.findByText("Couldn't add word.", { selector: "p" });
    expect(client.getQueryState(key)?.isInvalidated).toBe(false);
  });
});

describe("when things go wrong", () => {
  it("keeps the message, says the tutor is busy, and lets the learner try again", async () => {
    let n = 0;
    const { calls } = mockApi({
      ...base,
      "POST /chat": ({ body }: { body: { session_id: string } }) =>
        ++n === 1 ? err(429, "tutor_busy", "The tutor is busy. Try again in a moment.")() : { json: { reply: "Now it works.", tool_calls: [], session_id: body.session_id } },
    });
    renderApp("/chat");
    await say("hello");
    expect(await screen.findByText("The tutor is busy. Try again in a moment.")).toBeInTheDocument();
    expect(screen.getByText("hello")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Now it works.")).toBeInTheDocument();
    expect(screen.getAllByText("hello")).toHaveLength(1);                    // no duplicate bubble
    expect(screen.queryByText("The tutor is busy. Try again in a moment.")).not.toBeInTheDocument();
    expect(chatCalls(calls)).toHaveLength(2);
    expect(chatCalls(calls)[1].body).toEqual(chatCalls(calls)[0].body);       // same text, same session
  });

  it("shows the server's message when the tutor is not switched on", async () => {
    mockApi({ ...base, "POST /chat": err(503, "langflow_unavailable", "The chat tutor isn't switched on yet.") });
    renderApp("/chat");
    await say("hello");
    expect(await screen.findByText("The chat tutor isn't switched on yet.")).toBeInTheDocument();
  });

  it("explains a network failure", async () => {
    mockApi(base);
    const fetchMock = globalThis.fetch as unknown as (u: string, i?: RequestInit) => Promise<Response>;
    renderApp("/chat");
    await screen.findByLabelText("Message");
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => { if (init?.method === "POST") throw new TypeError("offline"); return fetchMock(url, init); }));
    await say("hello");
    expect(await screen.findByText(/Can't reach the server/)).toBeInTheDocument();
  });

  it("allows only one request at a time and says so when it is slow", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let release!: () => void;
    const held = new Promise<void>((r) => { release = r; });
    const { calls } = mockApi({ ...base, "POST /chat": ({ body }: { body: { session_id: string } }) => ({ json: { reply: "Finally.", tool_calls: [], session_id: body.session_id }, after: held }) });
    renderApp("/chat");
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    await user.type(await screen.findByLabelText("Message"), "slow one");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByRole("status")).toHaveTextContent(/thinking/i);
    expect(screen.queryByText(/still working/i)).not.toBeInTheDocument();

    await user.type(screen.getByLabelText("Message"), "second");
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    await user.type(screen.getByLabelText("Message"), "{Enter}");
    expect(chatCalls(calls)).toHaveLength(1);

    await act(async () => { vi.advanceTimersByTime(SLOW_AFTER_MS + 500); });
    expect(await screen.findByText(/still working/i)).toBeInTheDocument();

    release();
    expect(await screen.findByText("Finally.")).toBeInTheDocument();
    expect(screen.queryByText(/still working/i)).not.toBeInTheDocument();
  });
});

describe("conversations", () => {
  it("survive moving to another page and back", async () => {
    mockApi({ ...base, "POST /chat": reply("Hola!") });
    renderApp("/chat");
    await say("hello");
    await screen.findByText("Hola!");
    await userEvent.click(screen.getByRole("link", { name: "Vocabulary" }));
    await screen.findByRole("heading", { name: /^Vocabulary/ });
    await userEvent.click(screen.getByRole("link", { name: "Chat" }));
    expect(await screen.findByText("Hola!")).toBeInTheDocument();
    expect(screen.getByText("hello")).toBeInTheDocument();
  });

  it("start over with New chat, which uses a new session id", async () => {
    const { calls } = mockApi({ ...base, "POST /chat": reply("Hola!") });
    renderApp("/chat");
    await say("first");
    await screen.findByText("Hola!");
    await userEvent.click(screen.getByRole("button", { name: "New chat" }));
    expect(screen.queryByText("Hola!")).not.toBeInTheDocument();
    await say("second");
    await screen.findByText("Hola!");
    const [a, b] = chatCalls(calls).map((c) => c.body.session_id);
    expect(a).not.toBe(b);
  });

  it("are dropped at once when another person logs in on a second tab (one shared cookie)", async () => {
    let who: typeof ALICE = ALICE;
    mockApi({
      ...base,
      "GET /me": () => ({ json: who }),
      "POST /chat": ({ body }: { body: { session_id: string } }) =>
        who === ALICE
          ? { json: { reply: "Alice's private answer", tool_calls: [], session_id: body.session_id } }
          : err(401, "session_changed", "You are signed in as a different user in another tab.")(),
    });
    renderApp("/chat");
    await say("alice's private question");
    await screen.findByText("Alice's private answer");

    who = BOB as typeof ALICE;                               // another tab logged in as bob
    await say("intruder");
    await screen.findByText("Start a conversation");          // this tab now shows bob, with an empty chat
    expect(screen.queryByText(/alice's private/i)).not.toBeInTheDocument();
    expect(screen.queryByText("intruder")).not.toBeInTheDocument();
  });

  it("are never shown to the next person on the same browser", async () => {
    let who: typeof ALICE | null = ALICE;
    mockApi({
      ...base,
      "GET /me": () => (who ? { json: who } : err(401, "unauthorized", "Please log in.")()),
      "POST /chat": reply("Alice's private answer"),
      "POST /auth/logout": () => { who = null; return { status: 204 }; },
      "POST /auth/login": () => { who = BOB as typeof ALICE; return { json: BOB }; },
    });
    renderApp("/chat");
    await say("alice's private question");
    await screen.findByText("Alice's private answer");

    await userEvent.click(screen.getByRole("button", { name: "Log out" }));
    await screen.findByRole("button", { name: "Log in" });
    await userEvent.type(screen.getByLabelText("Email"), "bob@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "password123");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    await userEvent.click(await screen.findByRole("link", { name: "Chat" }));
    await screen.findByLabelText("Message");
    expect(screen.queryByText(/alice's private/i)).not.toBeInTheDocument();
  });

  describe("saving a story to the library", () => {
    const STORY_TEXT = "Ana: Hola.\nLuis: Hola, amigo.";
    const storyReply = reply("Here is a story.", [tool("Story Generator Tool", { language: "Spanish" }, STORY_TEXT)]);

    it("offers a save button for a story and sends the story, language and no type or topic", async () => {
      const { calls } = mockApi({ ...base, "POST /chat": storyReply, "POST /stories": () => ({ status: 201, json: { id: 1 } }) });
      renderApp("/chat");
      await say("tell me a story");
      await userEvent.click(await screen.findByRole("button", { name: "Save story to library" }));
      expect(await screen.findByRole("button", { name: "Saved" })).toBeDisabled();
      const save = calls.find((c) => c.method === "POST" && c.path === "/stories")!;
      expect(save.body).toEqual({ language: "en", body: STORY_TEXT, story_type: null, topic: null });
    });

    it("offers nothing for a reply without a story, a failed story or the tool's refusal message", async () => {
      mockApi({ ...base, "POST /chat": reply("Added.", [tool("Add Word", { word: "bread" }, "ok")]) });
      renderApp("/chat");
      await say("add the word bread");
      await screen.findByText("Added.");
      expect(screen.queryByRole("button", { name: /Save story/ })).not.toBeInTheDocument();
    });

    it("hides the button when the story tool failed or only returned its refusal", async () => {
      mockApi({ ...base, "POST /chat": reply("Sorry.", [tool("Story Generator Tool", {}, "Stories in German are not available yet.", true),
                                                       tool("Story Generator Tool", {}, "Stories in German are not available yet.")]) });
      renderApp("/chat");
      await say("story");
      await screen.findByText("Sorry.");
      expect(screen.queryByRole("button", { name: /Save story/ })).not.toBeInTheDocument();
    });

    it("offers nothing for a story the tool reported as failed", async () => {
      mockApi({ ...base, "POST /chat": reply("Hmm.", [tool("Story Generator Tool", {}, STORY_TEXT, true)]) });
      renderApp("/chat");
      await say("story");
      await screen.findByText("Hmm.");
      expect(screen.queryByRole("button", { name: /Save story/ })).not.toBeInTheDocument();
    });

    it("shows the API's error and keeps the button usable", async () => {
      mockApi({ ...base, "POST /chat": storyReply, "POST /stories": err(422, "library_full", "Your library holds 500 stories. Delete some to save more.") });
      renderApp("/chat");
      await say("story");
      await userEvent.click(await screen.findByRole("button", { name: "Save story to library" }));
      expect(await screen.findByText(/Your library holds 500 stories/)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Save story to library" })).toBeEnabled();
    });
  });
});
