import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuth } from "../auth/AuthContext";
import { AuthProvider } from "../auth/AuthContext";
import { ALICE, BOB, mockApi } from "../test/helpers";
import { ThemeProvider } from "../theme/ThemeProvider";
import { COPY_KEY, LEGACY_THEME_KEY, readCopy } from "./deviceCopy";
import { PreferencesProvider, usePreferences } from "./PreferencesProvider";

const COLORS = { page: "#eef6ff", cards: "#ffffff", text: "#0b2540", borders: "#c9dcf0", accent: "#0369a1" };
const saved = (o: object = {}) => ({ active_language: null, ui_follows_study_language: false, theme: "system", custom_colors: null, ...o });
const html = document.documentElement;

const rendered: string[] = [];      // every theme the screen was ever asked to show, in order

function Harness() {
  const { prefs, update, saveFailed, loggedIn } = usePreferences();
  rendered.push(prefs.theme);
  const { setUser } = useAuth();
  return (
    <div>
      <p>in:{String(loggedIn)} theme:{prefs.theme} lang:{prefs.active_language ?? "none"} follow:{String(prefs.ui_follows_study_language)}</p>
      {saveFailed && <p role="alert">not saved</p>}
      <button onClick={() => void update({ theme: "dark" })}>dark</button>
      <button onClick={() => void update({ theme: "light" })}>light</button>
      <button onClick={() => void update({ ui_follows_study_language: true })}>follow</button>
      <button onClick={() => void update({ custom_colors: COLORS })}>colors</button>
      <button onClick={() => setUser({ ...BOB, preferences: saved({ theme: "forest" }) } as never)}>become bob</button>
    </div>
  );
}

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <PreferencesProvider>
          <ThemeProvider><Harness /></ThemeProvider>
        </PreferencesProvider>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

const patches = (calls: { method: string; path: string; body: any }[]) => calls.filter((c) => c.method === "PATCH" && c.path === "/me/preferences");
const echo = (current: object = saved()) => {
  let state: any = { ...current };
  return ({ body }: { body: any }) => { state = { ...state, ...body }; return { json: state }; };
};
const me = (prefs: object | null, extra: object = {}) => ({ ...ALICE, languages: ["en", "es"], preferences: prefs, ...extra });

beforeEach(() => { localStorage.clear(); sessionStorage.clear(); html.classList.remove("dark"); html.removeAttribute("style"); });
afterEach(() => vi.unstubAllGlobals());

describe("preferences on the account (M8p)", () => {
  it("a signed-in learner sees the account's values", async () => {
    mockApi({ "GET /me": me(saved({ theme: "dark", active_language: "es", ui_follows_study_language: true })) });
    mount();
    expect(await screen.findByText("in:true theme:dark lang:es follow:true")).toBeInTheDocument();
    expect(html).toHaveClass("dark");
  });

  it("an account that never saved anything uses the defaults", async () => {
    mockApi({ "GET /me": me(null) });
    mount();
    expect(await screen.findByText("in:true theme:system lang:none follow:false")).toBeInTheDocument();
  });

  it("applies a change at once and saves once, after a short pause, with every change made in the meantime", async () => {
    const { calls } = mockApi({ "GET /me": me(saved()), "PATCH /me/preferences": echo() });
    mount();
    await screen.findByText(/in:true/);
    fireEvent.click(screen.getByText("dark"));
    expect(screen.getByText(/theme:dark/)).toBeInTheDocument();                      // before any request
    expect(html).toHaveClass("dark");
    expect(patches(calls)).toHaveLength(0);
    fireEvent.click(screen.getByText("follow"));
    fireEvent.click(screen.getByText("light"));
    await waitFor(() => expect(patches(calls)).toHaveLength(1), { timeout: 3000 });
    expect(patches(calls)[0].body).toEqual({ theme: "light", ui_follows_study_language: true });
    await new Promise((r) => setTimeout(r, 900));
    expect(patches(calls)).toHaveLength(1);                                           // nothing more is sent
    expect(screen.getByText(/theme:light/)).toBeInTheDocument();
  });

  it("a failed save keeps the look, says so, and the next change retries everything", async () => {
    let fail = true;
    const state = echo();
    const { calls } = mockApi({ "GET /me": me(saved()), "PATCH /me/preferences": (c: any) => (fail ? { status: 500, json: { error: { code: "internal_error", message: "x" } } } : state(c)) });
    mount();
    await screen.findByText(/in:true/);
    fireEvent.click(screen.getByText("dark"));
    expect(await screen.findByRole("alert", {}, { timeout: 3000 })).toHaveTextContent("not saved");
    expect(screen.getByText(/theme:dark/)).toBeInTheDocument();                       // the look stays
    fail = false;
    fireEvent.click(screen.getByText("follow"));
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull(), { timeout: 3000 });
    expect(patches(calls).at(-1)!.body).toEqual({ theme: "dark", ui_follows_study_language: true });
  });

  it("writes the device copy, and the init script applies exactly that", async () => {
    mockApi({ "GET /me": me(saved({ theme: "dark", custom_colors: COLORS })) });
    mount();
    await screen.findByText(/theme:dark/);
    await waitFor(() => expect(readCopy()).toMatchObject({ userId: 1, theme: "dark", custom_colors: COLORS }));
    html.classList.remove("dark");
    vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener() {}, removeEventListener() {} }));
    new Function(readFileSync("public/theme-init.js", "utf8"))();
    expect(html).toHaveClass("dark");
  });

  it("wipes the device copy when nobody is signed in", async () => {
    localStorage.setItem(COPY_KEY, JSON.stringify({ userId: 1, theme: "dark" }));
    mockApi({ "GET /me": () => ({ status: 401, json: { error: { code: "unauthorized", message: "no" } } }) });
    mount();
    await screen.findByText(/in:false/);
    await waitFor(() => expect(localStorage.getItem(COPY_KEY)).toBeNull());
  });

  it("a different person on the same browser replaces the copy and never inherits the previous theme", async () => {
    mockApi({ "GET /me": me(saved({ theme: "dark" })) });
    mount();
    await screen.findByText(/theme:dark/);
    await waitFor(() => expect(readCopy()?.theme).toBe("dark"));
    fireEvent.click(screen.getByText("become bob"));
    await screen.findByText(/theme:forest/);
    await waitFor(() => expect(readCopy()).toMatchObject({ userId: 2, theme: "forest" }));
  });

  it("an unsaved change made by one person is never saved into the next person's account", async () => {
    const { calls } = mockApi({ "GET /me": me(saved()), "PATCH /me/preferences": echo() });
    mount();
    await screen.findByText(/in:true/);
    fireEvent.click(screen.getByText("dark"));                                        // pending, not yet sent
    rendered.length = 0;
    fireEvent.click(screen.getByText("become bob"));
    await new Promise((r) => setTimeout(r, 1000));
    expect(patches(calls)).toHaveLength(0);
    expect(screen.getByText(/theme:forest/)).toBeInTheDocument();                     // bob's own value, not alice's override
    expect(rendered).not.toContain("dark");                                           // not even for one frame
  });

  it("another tab changing the copy for the same person updates this one", async () => {
    mockApi({ "GET /me": me(saved()) });
    mount();
    await screen.findByText(/in:true theme:system/);
    act(() => {
      localStorage.setItem(COPY_KEY, JSON.stringify({ userId: 1, theme: "dark", active_language: "es", ui_follows_study_language: true, custom_colors: null }));
      window.dispatchEvent(new StorageEvent("storage", { key: COPY_KEY }));
    });
    expect(await screen.findByText("in:true theme:dark lang:es follow:true")).toBeInTheDocument();
  });

  it("a copy that belongs to somebody else is ignored", async () => {
    mockApi({ "GET /me": me(saved()) });
    mount();
    await screen.findByText(/in:true theme:system/);
    act(() => {
      localStorage.setItem(COPY_KEY, JSON.stringify({ userId: 99, theme: "dark" }));
      window.dispatchEvent(new StorageEvent("storage", { key: COPY_KEY }));
    });
    await new Promise((r) => setTimeout(r, 300));
    expect(screen.getByText(/theme:system/)).toBeInTheDocument();
  });

  describe("device-only settings from the first design", () => {
    it("are uploaded once, then removed", async () => {
      localStorage.setItem(LEGACY_THEME_KEY, "dark");
      localStorage.setItem("tutor:lang:1", "es");
      const { calls } = mockApi({ "GET /me": me(null), "PATCH /me/preferences": echo() });
      mount();
      await waitFor(() => expect(patches(calls)).toHaveLength(1));
      expect(patches(calls)[0].body).toEqual({ theme: "dark", active_language: "es" });
      await waitFor(() => expect(localStorage.getItem(LEGACY_THEME_KEY)).toBeNull());
      expect(localStorage.getItem("tutor:lang:1")).toBeNull();
      expect(await screen.findByText(/theme:dark lang:es/)).toBeInTheDocument();
    });

    it("are not used when the account already has its own preferences, and are cleaned up", async () => {
      localStorage.setItem(LEGACY_THEME_KEY, "dark");
      const { calls } = mockApi({ "GET /me": me(saved({ theme: "light" })) });
      mount();
      await screen.findByText(/theme:light/);
      await waitFor(() => expect(localStorage.getItem(LEGACY_THEME_KEY)).toBeNull());
      expect(patches(calls)).toHaveLength(0);
    });

    it("junk and a language the learner does not study are ignored", async () => {
      localStorage.setItem(LEGACY_THEME_KEY, "purple");
      localStorage.setItem("tutor:lang:1", "ja");
      const { calls } = mockApi({ "GET /me": me(null), "PATCH /me/preferences": echo() });
      mount();
      await screen.findByText(/in:true theme:system/);
      await waitFor(() => expect(localStorage.getItem(LEGACY_THEME_KEY)).toBeNull());
      expect(patches(calls)).toHaveLength(0);
    });

    it("stay where they are if the upload fails, so nothing is lost", async () => {
      localStorage.setItem(LEGACY_THEME_KEY, "dark");
      mockApi({ "GET /me": me(null), "PATCH /me/preferences": () => ({ status: 500, json: { error: { code: "internal_error", message: "x" } } }) });
      mount();
      await screen.findByRole("alert");
      expect(localStorage.getItem(LEGACY_THEME_KEY)).toBe("dark");
    });
  });
});

describe("theme-init.js with the device copy", () => {
  const script = readFileSync("public/theme-init.js", "utf8");
  const run = (copy: unknown, osDark: boolean) => {
    html.classList.remove("dark");
    html.removeAttribute("style");
    vi.stubGlobal("matchMedia", () => ({ matches: osDark, addEventListener() {}, removeEventListener() {} }));
    if (copy === null) localStorage.removeItem(COPY_KEY); else localStorage.setItem(COPY_KEY, typeof copy === "string" ? copy : JSON.stringify(copy));
    new Function(script)();
    return html.classList.contains("dark");
  };
  it("follows the same rules as the provider", () => {
    expect(run(null, true)).toBe(true);                                   // no copy: follow the OS
    expect(run(null, false)).toBe(false);
    expect(run({ userId: 1, theme: "system" }, true)).toBe(true);
    expect(run({ userId: 1, theme: "dark" }, false)).toBe(true);          // explicit choices beat the OS
    expect(run({ userId: 1, theme: "light" }, true)).toBe(false);
    expect(run({ userId: 1, theme: "some-future-id" }, true)).toBe(true); // an id it does not know means System
    expect(run("{not json", false)).toBe(false);
  });
  it("with no copy, applies this tab's light/dark switch; with a copy, the tab key is ignored", () => {
    sessionStorage.setItem("tutor:theme:tab", "light");
    expect(run(null, true)).toBe(false);
    sessionStorage.setItem("tutor:theme:tab", "dark");
    expect(run(null, false)).toBe(true);
    expect(run({ userId: 1, theme: "light" }, false)).toBe(false);        // someone is signed in: their copy decides
    sessionStorage.setItem("tutor:theme:tab", "junk");
    expect(run(null, true)).toBe(true);
    sessionStorage.clear();
  });
  it("applies a finished colour map and base with no maths of its own", () => {
    const dark = run({ userId: 1, theme: "ocean", base: "dark", vars: { "--color-surface": "#123456", "--color-slate-50": "#010203" } }, false);
    expect(dark).toBe(true);
    expect(html.style.getPropertyValue("--color-surface")).toBe("#123456");
    expect(html.style.getPropertyValue("--color-slate-50")).toBe("#010203");
  });
  it("only ever sets custom properties", () => {
    run({ userId: 1, theme: "x", base: "light", vars: { "color": "red", "--color-ok": "#fff" } }, false);
    expect(html.style.getPropertyValue("color")).toBe("");
    expect(html.style.getPropertyValue("--color-ok")).toBe("#fff");
  });
  it("survives blocked storage", () => {
    vi.stubGlobal("matchMedia", () => ({ matches: true, addEventListener() {}, removeEventListener() {} }));
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    expect(() => new Function(script)()).not.toThrow();
    vi.restoreAllMocks();
  });
});
