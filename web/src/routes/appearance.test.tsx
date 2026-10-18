import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ALICE, LANGS, mockApi, renderApp } from "../test/helpers";

const html = document.documentElement;
const prefs = (theme: string, custom: unknown = null) => ({ active_language: null, ui_follows_study_language: false, theme, custom_colors: custom });
const HEALTH = { postgres: { ok: true }, langflow: { ok: true }, groq: { ok: null } };
const CUSTOM = { page: "#ffffff", cards: "#ffffff", text: "#000000", borders: "#cccccc", accent: "#4f46e5" };

function open(theme: string, custom: unknown = null) {
  return mockApi({
    "GET /me": { ...ALICE, preferences: prefs(theme, custom) }, "GET /languages": LANGS, "GET /health": HEALTH,
    "PATCH /me/preferences": ({ body }: any) => ({ json: { ...prefs("system"), ...body } }),
  });
}
const patches = (calls: any[]) => calls.filter((c) => c.method === "PATCH").map((c) => c.body);
beforeEach(() => { localStorage.clear(); html.removeAttribute("style"); html.classList.remove("dark"); });
afterEach(() => vi.restoreAllMocks());

describe("settings: appearance", () => {
  it("offers Light, Dark, System, the seven presets and Custom as one group", async () => {
    open("system");
    renderApp("/settings");
    const group = await screen.findByRole("radiogroup", { name: "Theme" });
    const names = [...group.querySelectorAll("input")].map((i) => i.closest("label")!.textContent);
    expect(names).toEqual(["Light", "Dark", "System", "Ocean", "Forest", "Sunset", "Rose", "Midnight", "Graphite", "High contrast", "Custom"]);
  });

  it("picking a preset applies it at once and saves its id", async () => {
    const { calls } = open("system");
    renderApp("/settings");
    await userEvent.click(await screen.findByRole("radio", { name: "Midnight" }));
    expect(html.style.getPropertyValue("--color-slate-50")).toBe("#070b1a");
    expect(html).toHaveClass("dark");
    await waitFor(() => expect(patches(calls)).toEqual([{ theme: "midnight" }]), { timeout: 3000 });
  });

  it("the editor is hidden until Custom is chosen", async () => {
    open("ocean");
    renderApp("/settings");
    await screen.findByRole("radio", { name: "Ocean" });
    expect(screen.queryByText("Customize colors")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: "Custom" }));
    expect(await screen.findByText("Customize colors")).toBeInTheDocument();
  });

  it("typing a hex colour changes the part, saves the five colours, and ignores a bad value", async () => {
    const { calls } = open("custom", CUSTOM);
    renderApp("/settings");
    const hex = await screen.findByLabelText("Hex color");
    await userEvent.clear(hex);
    await userEvent.type(hex, "#zzz");
    expect(hex).toHaveAttribute("aria-invalid", "true");
    expect(html.style.getPropertyValue("--color-slate-50")).toBe("#ffffff");
    await userEvent.clear(hex);
    await userEvent.type(hex, "#abc");
    await waitFor(() => expect(html.style.getPropertyValue("--color-slate-50")).toBe("#aabbcc"));
    await waitFor(() => expect(patches(calls).at(-1)).toEqual({ theme: "custom", custom_colors: { ...CUSTOM, page: "#aabbcc" } }), { timeout: 3000 });
  });

  it("choosing another part points the wheel and hex box at that part", async () => {
    open("custom", CUSTOM);
    renderApp("/settings");
    const hex = await screen.findByLabelText("Hex color");
    expect(hex).toHaveValue("#ffffff");
    await userEvent.click(screen.getByRole("radio", { name: "Borders" }));
    expect(hex).toHaveValue("#cccccc");
    expect(screen.getByRole("slider", { name: "Color wheel: Borders" })).toBeInTheDocument();
  });

  it("the wheel works from the keyboard and says its value", async () => {
    open("custom", { ...CUSTOM, accent: "#ff0000" });
    renderApp("/settings");
    await userEvent.click(await screen.findByRole("radio", { name: "Buttons, links and menu" }));
    const wheel = screen.getByRole("slider", { name: "Color wheel: Buttons, links and menu" });
    expect(wheel).toHaveAttribute("aria-valuetext", "Hue 0 degrees, strength 100 percent");
    wheel.focus();
    await userEvent.keyboard("{Shift>}{ArrowRight}{/Shift}");
    expect(await screen.findByLabelText("Hex color")).not.toHaveValue("#ff0000");
    expect(wheel).toHaveAttribute("aria-valuenow", "15");
  });

  it("the readability panel shows real ratios and warns, and says when the button colour was darkened", async () => {
    open("custom", { ...CUSTOM, text: "#eeeeee", accent: "#ffee00" });
    renderApp("/settings");
    const panel = (await screen.findByText("Readability")).parentElement!;
    expect(panel).toHaveTextContent("Text on page");
    expect(panel).toHaveTextContent(/1\.2:1\s*Hard to read/);
    expect(panel).toHaveTextContent("Button text");
    expect(screen.getByText(/button color was darkened/i)).toBeInTheDocument();
  });

  it("Reset colors returns to the starting palette; Start from copies a preset", async () => {
    const { calls } = open("custom", { ...CUSTOM, page: "#123456" });
    renderApp("/settings");
    await userEvent.selectOptions(await screen.findByLabelText("Start from"), "Forest");
    await waitFor(() => expect(html.style.getPropertyValue("--color-slate-50")).toBe("#f1f7f0"));
    await userEvent.click(screen.getByRole("button", { name: "Reset colors" }));
    await waitFor(() => expect(html.style.getPropertyValue("--color-slate-50")).toBe("#eef6ff"));
    await waitFor(() => expect(patches(calls).at(-1).custom_colors.page).toBe("#eef6ff"), { timeout: 3000 });
  });
});
