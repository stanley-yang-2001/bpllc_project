import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { readFileSync } from "node:fs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ThemeToggle } from "../components/ThemeToggle";
import { ThemeProvider, THEME_KEY, useTheme } from "./ThemeProvider";

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

beforeEach(() => { localStorage.clear(); html.classList.remove("dark"); });
afterEach(() => { vi.unstubAllGlobals(); });

describe("theme provider", () => {
  it("defaults to the system setting and follows it live", () => {
    const os = fakeOs(true);
    render(<ThemeProvider><Probe /></ThemeProvider>);
    expect(screen.getByText("system/dark")).toBeInTheDocument();
    expect(html).toHaveClass("dark");
    act(() => os.set(false));
    expect(screen.getByText("system/light")).toBeInTheDocument();
    expect(html).not.toHaveClass("dark");
  });

  it("an explicit choice wins over the system and is remembered", async () => {
    fakeOs(true);
    render(<ThemeProvider><ThemeToggle /><Probe /></ThemeProvider>);
    await userEvent.click(screen.getByRole("button", { name: "Switch to light mode" }));
    expect(screen.getByText("light/light")).toBeInTheDocument();
    expect(html).not.toHaveClass("dark");
    expect(localStorage.getItem(THEME_KEY)).toBe("light");
    await userEvent.click(screen.getByRole("button", { name: "Switch to dark mode" }));
    expect(html).toHaveClass("dark");
    expect(localStorage.getItem(THEME_KEY)).toBe("dark");
  });

  it("a saved choice is used on the next visit, and junk in storage is ignored", () => {
    fakeOs(false);
    localStorage.setItem(THEME_KEY, "dark");
    const first = render(<ThemeProvider><Probe /></ThemeProvider>);
    expect(screen.getByText("dark/dark")).toBeInTheDocument();
    first.unmount();
    localStorage.setItem(THEME_KEY, "purple");
    render(<ThemeProvider><Probe /></ThemeProvider>);
    expect(screen.getByText("system/light")).toBeInTheDocument();
  });

  it("another tab changing the theme updates this one", () => {
    fakeOs(false);
    render(<ThemeProvider><Probe /></ThemeProvider>);
    act(() => { localStorage.setItem(THEME_KEY, "dark"); window.dispatchEvent(new StorageEvent("storage", { key: THEME_KEY })); });
    expect(screen.getByText("dark/dark")).toBeInTheDocument();
    expect(html).toHaveClass("dark");
  });

  it("the toggle's label names the action, not the state", () => {
    fakeOs(false);
    render(<ThemeProvider><ThemeToggle /></ThemeProvider>);
    expect(screen.getByRole("button", { name: "Switch to dark mode" })).toBeInTheDocument();
  });
});

describe("theme-init.js (runs before first paint)", () => {
  const script = readFileSync("public/theme-init.js", "utf8");
  const run = (saved: string | null, osDark: boolean) => {
    html.classList.remove("dark");
    fakeOs(osDark);
    if (saved === null) localStorage.removeItem(THEME_KEY); else localStorage.setItem(THEME_KEY, saved);
    new Function(script)();
    return html.classList.contains("dark");
  };
  it("matches the provider's rules", () => {
    expect(run(null, true)).toBe(true);         // nothing saved: follow the OS
    expect(run(null, false)).toBe(false);
    expect(run("system", true)).toBe(true);
    expect(run("dark", false)).toBe(true);      // explicit choices beat the OS
    expect(run("light", true)).toBe(false);
    expect(run("purple", false)).toBe(false);   // junk: light
  });
  it("survives blocked storage", () => {
    fakeOs(true);
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    expect(() => new Function(script)()).not.toThrow();
  });
});
