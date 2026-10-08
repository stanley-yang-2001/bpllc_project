import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { installBfcacheGuard } from "./bfcache";
import { ALICE, BOB, err, LANGS, mockApi, renderApp } from "../test/helpers";

const W = (id: number, word: string) => ({ id, language: "en", word, meaning: null, created_at: "2026-01-01T00:00:00Z" });
const page = (...w: ReturnType<typeof W>[]) => ({ items: w, total: w.length, limit: 50, offset: 0 });

afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });

/** Stand-in for BroadcastChannel so a test can play "another tab". */
class FakeChannel {
  static all: FakeChannel[] = [];
  onmessage: ((e: { data: unknown }) => void) | null = null;
  constructor(public name: string) { FakeChannel.all.push(this); }
  postMessage(data: unknown) { FakeChannel.all.filter((c) => c !== this && c.name === this.name).forEach((c) => c.onmessage?.({ data })); }
  close() { FakeChannel.all = FakeChannel.all.filter((c) => c !== this); }
}

describe("shared browser: one person after another", () => {
  it("sends the expected-user header on data requests, but not when asking who is logged in", async () => {
    const { calls } = mockApi({ "GET /me": ALICE, "GET /languages": LANGS, "GET /words": page(W(1, "alicesword")) });
    renderApp("/vocabulary");
    await screen.findByText("alicesword");
    expect(calls.find((c) => c.path === "/me")!.headers["X-Expected-User"]).toBeUndefined();
    expect(calls.find((c) => c.path.startsWith("/words"))!.headers["X-Expected-User"]).toBe("1");
  });

  it("user B never sees user A's words after A logs out and B logs in", async () => {
    let who: typeof ALICE | null = ALICE;
    mockApi({
      "GET /me": () => (who ? { json: who } : err(401, "unauthorized", "Please log in.")()),
      "GET /languages": LANGS,
      "GET /words": () => ({ json: page(who === ALICE ? W(1, "alicesecret") : W(9, "bobsword")) }),
      "POST /auth/logout": () => { who = null; return { status: 204 }; },
      "POST /auth/login": () => { who = BOB as typeof ALICE; return { json: BOB }; },
    });
    const { client } = renderApp("/vocabulary");
    await screen.findByText("alicesecret");

    await userEvent.click(screen.getByRole("button", { name: "Log out" }));
    await screen.findByRole("button", { name: "Log in" });
    expect(screen.queryByText("alicesecret")).not.toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Email"), "bob@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "password123");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    await userEvent.click(await screen.findByRole("link", { name: "Vocabulary" }));
    await screen.findByText("bobsword");
    expect(screen.queryByText("alicesecret")).not.toBeInTheDocument();
    expect(client.getQueryCache().findAll({ predicate: (q) => q.queryKey[1] === 1 })).toHaveLength(0);   // nothing keyed to A
  });

  it("logging in as someone else without logging out first still drops the previous person's data", async () => {
    const { QueryClient, QueryClientProvider } = await import("@tanstack/react-query");
    const { render } = await import("@testing-library/react");
    const { AuthProvider, useAuth } = await import("./AuthContext");
    const { wordsKey } = await import("../api/keys");
    const { api } = await import("../api/client");
    const { calls } = mockApi({ "GET /me": ALICE, "GET /words": page() });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    function Probe() {                       // stands in for the login form succeeding as a different user
      const { user, setUser } = useAuth();
      return <button onClick={() => setUser(BOB)}>{user ? `as ${user.display_name}` : "loading"}</button>;
    }
    render(<QueryClientProvider client={client}><AuthProvider><Probe /></AuthProvider></QueryClientProvider>);
    await screen.findByRole("button", { name: "as Alice" });
    client.setQueryData(wordsKey(1, "en"), page(W(1, "alicesecret")));
    expect(client.getQueryData(wordsKey(1, "en"))).toBeTruthy();

    await userEvent.click(screen.getByRole("button", { name: "as Alice" }));
    await screen.findByRole("button", { name: "as Bob" });
    expect(client.getQueryData(wordsKey(1, "en"))).toBeUndefined();           // alice's cached words are gone
    expect(client.getQueryCache().findAll({ predicate: (q) => q.queryKey[0] !== "me" })).toHaveLength(0);
    await api.words({ language: "en" });                                      // and requests now identify bob
    expect(calls.at(-1)!.headers["X-Expected-User"]).toBe("2");
  });

  it("cache keys are scoped to the user: a leftover entry for another person is never displayed", async () => {
    // Defence in depth. Even if clearing the cache were ever skipped, bob's page must not read alice's entry.
    const { QueryClient } = await import("@tanstack/react-query");
    const { wordsKey } = await import("../api/keys");
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    client.setQueryData(["me"], BOB);
    client.setQueryData(wordsKey(1, "en", "", 0), page(W(1, "alicesecret")));      // key of user 1 (alice)
    mockApi({ "GET /me": BOB, "GET /languages": LANGS, "GET /words": page(W(9, "bobsword")) });
    renderApp("/vocabulary", client);
    expect(screen.queryByText("alicesecret")).not.toBeInTheDocument();            // not even for a single render
    await screen.findByText("bobsword");
    expect(screen.queryByText("alicesecret")).not.toBeInTheDocument();
  });

  it("a slow response for A that arrives after B has logged in is never shown to B", async () => {
    let who: typeof ALICE | null = ALICE;
    let release!: () => void;
    const slow = new Promise<void>((r) => { release = r; });
    let firstWordsCall = true;
    mockApi({
      "GET /me": () => (who ? { json: who } : err(401, "unauthorized", "x")()),
      "GET /languages": LANGS,
      "GET /words": () => {
        if (firstWordsCall) { firstWordsCall = false; return { json: page(W(1, "latealice")), after: slow }; }   // A's request hangs
        return { json: page(W(9, "bobsword")) };
      },
      "POST /auth/logout": () => { who = null; return { status: 204 }; },
      "POST /auth/login": () => { who = BOB as typeof ALICE; return { json: BOB }; },
    });
    renderApp("/vocabulary");
    await userEvent.click(await screen.findByRole("button", { name: "Log out" }));
    await userEvent.type(await screen.findByLabelText("Email"), "bob@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "password123");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    await userEvent.click(await screen.findByRole("link", { name: "Vocabulary" }));
    await screen.findByText("bobsword");

    release();                                             // A's response finally arrives
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText("latealice")).not.toBeInTheDocument();
    expect(screen.getByText("bobsword")).toBeInTheDocument();
  });
});

describe("two tabs, one cookie", () => {
  it("a request refused with session_changed drops A's data at once and adopts whoever is signed in", async () => {
    let who: typeof ALICE = ALICE;
    mockApi({
      "GET /me": () => ({ json: who }),
      "GET /languages": LANGS,
      "GET /words": () => ({ json: page(who === ALICE ? W(1, "alicesecret") : W(9, "bobsword")) }),
      "POST /words": err(401, "session_changed", "You are signed in as a different user in another tab."),
    });
    renderApp("/vocabulary");
    await screen.findByText("alicesecret");
    who = BOB as typeof ALICE;                              // another tab logged in as bob (shared cookie)
    await userEvent.type(screen.getByLabelText("Word"), "intruder");
    await userEvent.click(screen.getByRole("button", { name: "Add word" }));
    await screen.findByText("bobsword");                     // tab now shows the person who is really logged in
    expect(screen.queryByText("alicesecret")).not.toBeInTheDocument();
    expect(screen.getByText("Bob")).toBeInTheDocument();
  });

  it("a session that ended elsewhere sends the page to the login screen", async () => {
    let live = true;
    mockApi({
      "GET /me": () => (live ? { json: ALICE } : err(401, "unauthorized", "Please log in.")()),
      "GET /languages": LANGS,
      "GET /words": () => (live ? { json: page(W(1, "alicesecret")) } : err(401, "unauthorized", "Please log in.")()),
      "POST /words": err(401, "unauthorized", "Please log in."),
    });
    renderApp("/vocabulary");
    await screen.findByText("alicesecret");
    live = false;                                           // e.g. "Log out everywhere" on another device
    await userEvent.type(screen.getByLabelText("Word"), "x");
    await userEvent.click(screen.getByRole("button", { name: "Add word" }));
    expect(await screen.findByRole("button", { name: "Log in" })).toBeInTheDocument();
    expect(screen.queryByText("alicesecret")).not.toBeInTheDocument();
  });

  it("logging out in one tab logs the other tab out", async () => {
    vi.stubGlobal("BroadcastChannel", FakeChannel);
    let live = true;
    mockApi({
      "GET /me": () => (live ? { json: ALICE } : err(401, "unauthorized", "Please log in.")()),
      "GET /languages": LANGS,
      "GET /words": page(W(1, "alicesecret")),
    });
    renderApp("/vocabulary");
    await screen.findByText("alicesecret");
    live = false;
    new FakeChannel("tutor-auth").postMessage("changed");   // the other tab announces a change
    expect(await screen.findByRole("button", { name: "Log in" })).toBeInTheDocument();
    expect(screen.queryByText("alicesecret")).not.toBeInTheDocument();
  });

  it("announces its own logout so other tabs can react", async () => {
    vi.stubGlobal("BroadcastChannel", FakeChannel);
    mockApi({ "GET /me": ALICE, "GET /languages": LANGS, "GET /words": page(), "POST /auth/logout": () => ({ status: 204 }) });
    const heard = vi.fn();
    renderApp("/");
    const otherTab = new FakeChannel("tutor-auth");
    otherTab.onmessage = heard;
    await userEvent.click(await screen.findByRole("button", { name: "Log out" }));
    await waitFor(() => expect(heard).toHaveBeenCalled());
  });
});

describe("log out everywhere", () => {
  it("calls the server and returns to the login screen", async () => {
    const { calls } = mockApi({ "GET /me": ALICE, "GET /languages": LANGS, "GET /health": { postgres: { ok: true }, langflow: {}, groq: {}, ai_mode: "live" }, "POST /auth/logout-all": () => ({ status: 204 }) });
    renderApp("/settings");
    await userEvent.click(await screen.findByRole("button", { name: "Log out everywhere" }));
    expect(await screen.findByRole("button", { name: "Log in" })).toBeInTheDocument();
    expect(calls.some((c) => c.path === "/auth/logout-all" && c.method === "POST")).toBe(true);
  });
});

describe("back/forward cache", () => {
  it("reloads a page the browser restored from memory, and ignores a normal load", () => {
    const listeners: Record<string, (e: unknown) => void> = {};
    const reload = vi.fn();
    installBfcacheGuard({ addEventListener: (t: string, fn: any) => { listeners[t] = fn; } } as any, reload);
    listeners.pageshow({ persisted: false });
    expect(reload).not.toHaveBeenCalled();
    listeners.pageshow({ persisted: true });
    expect(reload).toHaveBeenCalledTimes(1);
  });
});
