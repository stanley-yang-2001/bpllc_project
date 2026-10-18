import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth/AuthContext";
import { ThemeToggle } from "../components/ThemeToggle";
import { ActiveLanguageProvider } from "../auth/ActiveLanguage";
import { I18nProvider } from "../i18n/I18nProvider";
import { PreferencesProvider } from "../prefs/PreferencesProvider";
import { ALICE, mockApi } from "../test/helpers";
import { ThemeProvider, TEMP_THEME_KEY, asTheme, useTheme } from "./ThemeProvider";

/** A controllable stand-in for the operating system's light/dark setting. */
function fakeOs(initialDark: boolean) {
  let dark = initialDark;
  const listeners = new Set<() => void>();
  vi.stubGlobal("matchMedia", (q: string) => ({
    matches: q.includes("dark") ? dark : false,
    addEventListener: (_: string, fn: () => void) => listeners.add(fn),
    removeEventListener: (_: string, fn: () => void) => listeners.delete(fn),
  }));
  return { set(v: boolean) { dark = v; listeners.forEach((l) => l()); } };
}

const Probe = () => { const { theme, resolved } = useTheme(); return <p>{theme}/{resolved}</p>; };
const html = document.documentElement;
const saved = (theme: string) => ({ active_language: null, ui_follows_study_language: false, theme, custom_colors: null });

function mount(me: unknown) {
  const calls = mockApi({
    "GET /me": me === null ? () => ({ status: 401, json: { error: { code: "unauthorized", message: "no" } } }) : me,
    "PATCH /me/preferences": ({ body }: any) => ({ json: { ...saved("system"), ...body } }),
  }).calls;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AuthProvider><PreferencesProvider><ActiveLanguageProvider><I18nProvider><ThemeProvider><ThemeToggle /><Probe /></ThemeProvider></I18nProvider></ActiveLanguageProvider></PreferencesProvider></AuthProvider>
    </QueryClientProvider>,
  );
  return calls;
}

beforeEach(() => { localStorage.clear(); sessionStorage.clear(); html.classList.remove("dark"); });
afterEach(() => { vi.unstubAllGlobals(); });

describe("theme provider, signed out (the sign-in and policy pages)", () => {
  it("follows the operating system, live", async () => {
    const os = fakeOs(true);
    mount(null);
    expect(await screen.findByText("system/dark")).toBeInTheDocument();
    expect(html).toHaveClass("dark");
    act(() => os.set(false));
    expect(screen.getByText("system/light")).toBeInTheDocument();
    expect(html).not.toHaveClass("dark");
  });

  it("the switch works for this tab only: nothing goes to the account or to local storage", async () => {
    fakeOs(true);
    const calls = mount(null);
    await userEvent.click(await screen.findByRole("button", { name: "Switch to light mode" }));
    expect(screen.getByText("light/light")).toBeInTheDocument();
    expect(sessionStorage.getItem(TEMP_THEME_KEY)).toBe("light");
    expect(localStorage.length).toBe(0);
    expect(calls.filter((c) => c.method === "PATCH")).toHaveLength(0);
  });

  it("ignores any stored account preferences or old device settings", async () => {
    fakeOs(false);
    localStorage.setItem("tutor:theme", "dark");
    localStorage.setItem("tutor:prefs:cache", JSON.stringify({ userId: 1, theme: "dark" }));
    mount(null);
    expect(await screen.findByText("system/light")).toBeInTheDocument();
    expect(html).not.toHaveClass("dark");
  });
});

describe("theme provider, signed in", () => {
  it("shows the account's theme and a stored value is never consulted", async () => {
    fakeOs(false);
    localStorage.setItem("tutor:theme", "light");
    mount({ ...ALICE, preferences: saved("dark") });
    expect(await screen.findByText("dark/dark")).toBeInTheDocument();
    expect(html).toHaveClass("dark");
  });

  it("an explicit choice wins over the system and is saved to the account", async () => {
    fakeOs(true);
    const calls = mount({ ...ALICE, preferences: null });
    await userEvent.click(await screen.findByRole("button", { name: "Switch to light mode" }));
    expect(screen.getByText("light/light")).toBeInTheDocument();
    expect(html).not.toHaveClass("dark");
    await waitFor(() => expect(calls.filter((c) => c.method === "PATCH").map((c) => c.body)).toEqual([{ theme: "light" }]), { timeout: 3000 });
  });

  it("a theme id this version does not know falls back to System", async () => {
    fakeOs(true);
    mount({ ...ALICE, preferences: saved("some-future-id") });
    expect(await screen.findByText("system/dark")).toBeInTheDocument();
  });

  it("the toggle's label names the action, not the state", async () => {
    fakeOs(false);
    mount({ ...ALICE, preferences: null });
    expect(await screen.findByRole("button", { name: "Switch to dark mode" })).toBeInTheDocument();
  });
});

describe("asTheme", () => {
  it("keeps the built-ins, the presets and custom, and turns everything else into system", () => {
    expect(["light", "dark", "system", "ocean", "custom", "midnight", "nope", "", null, 5].map(asTheme)).toEqual(["light", "dark", "system", "ocean", "custom", "midnight", "system", "system", "system", "system"]);
  });
});


describe("theme provider, presets and custom colours", () => {
  const style = (n: string) => html.style.getPropertyValue(n);
  beforeEach(() => { html.removeAttribute("style"); });

  it("a preset sets the variables and the base, and writes the finished map to the device copy for the init script", async () => {
    fakeOs(false);
    mount({ ...ALICE, preferences: saved("midnight") });
    expect(await screen.findByText("midnight/dark")).toBeInTheDocument();
    expect(style("--color-slate-50")).toBe("#070b1a");
    expect(style("--color-brand-600")).toBe("#4f46e5");
    expect(html).toHaveClass("dark");
    await waitFor(() => {
      const copy = JSON.parse(localStorage.getItem("tutor:prefs:cache")!);
      expect(copy.base).toBe("dark");
      expect(copy.vars["--color-slate-50"]).toBe("#070b1a");
      expect(copy.theme).toBe("midnight");
    });
  });

  it("choosing Light, Dark or System removes every inline variable and clears them from the copy", async () => {
    fakeOs(false);
    mount({ ...ALICE, preferences: saved("ocean") });
    await screen.findByText("ocean/light");
    expect(style("--color-slate-50")).toBe("#eef6ff");
    await userEvent.click(screen.getByRole("button", { name: "Switch to dark mode" }));
    expect(await screen.findByText("dark/dark")).toBeInTheDocument();
    expect(html.getAttribute("style") ?? "").not.toContain("--color");
    await waitFor(() => expect(JSON.parse(localStorage.getItem("tutor:prefs:cache")!).vars).toBeNull());
  });

  it("the header switch from a dark preset goes to Light, and from a light preset to Dark", async () => {
    fakeOs(false);
    mount({ ...ALICE, preferences: saved("midnight") });
    await userEvent.click(await screen.findByRole("button", { name: "Switch to light mode" }));
    expect(await screen.findByText("light/light")).toBeInTheDocument();
  });

  it("custom uses the learner's five colours; bad stored colours fall back to the starting palette", async () => {
    fakeOs(false);
    mount({ ...ALICE, preferences: { ...saved("custom"), custom_colors: { page: "#ffffff", cards: "#ffffff", text: "#000000", borders: "#cccccc", accent: "#ffee00" } } });
    await screen.findByText("custom/light");
    expect(style("--color-slate-50")).toBe("#ffffff");
    // the accent was darkened until white button text is readable, so it is not the picked yellow
    expect(style("--color-brand-600")).not.toBe("#ffee00");
  });
  it("custom with no valid colours uses the starting palette", async () => {
    fakeOs(false);
    mount({ ...ALICE, preferences: { ...saved("custom"), custom_colors: null } });
    await screen.findByText("custom/light");
    expect(style("--color-slate-50")).toBe("#eef6ff");
  });

  it("signed out, leftover variables from an earlier session are removed", async () => {
    fakeOs(false);
    html.style.setProperty("--color-slate-50", "#070b1a");
    html.classList.add("dark");
    mount(null);
    await screen.findByText("system/light");
    expect(style("--color-slate-50")).toBe("");
    expect(html).not.toHaveClass("dark");
  });
});
