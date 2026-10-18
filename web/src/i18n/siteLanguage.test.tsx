import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ALICE, LANGS, mockApi, renderApp } from "../test/helpers";

afterEach(() => { vi.restoreAllMocks(); document.documentElement.lang = ""; });
const prefs = (follows: boolean, active = "ja") => ({ active_language: active, ui_follows_study_language: follows, theme: "system", custom_colors: null });
const me = (follows: boolean) => ({ ...ALICE, languages: ["en", "ja"], preferences: prefs(follows) });
const words = { items: [], total: 0, limit: 50, offset: 0 };

describe("the site in the study language", () => {
  it("shows menus and page text in Japanese and sets <html lang> when switched on", async () => {
    mockApi({ "GET /me": me(true), "GET /languages": LANGS, "GET /words": words });
    renderApp("/vocabulary");
    expect(await screen.findByRole("link", { name: "ホーム" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "メイン" })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("ja");
  });
  it("stays English when switched off, even with Japanese as the study language", async () => {
    mockApi({ "GET /me": me(false), "GET /languages": LANGS, "GET /words": words });
    renderApp("/vocabulary");
    expect(await screen.findByRole("link", { name: "Home" })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("en");
  });
  it("the sign-in page is English when nobody is signed in", async () => {
    mockApi({ "GET /me": () => ({ status: 401, json: { error: { code: "unauthorized", message: "no" } } }), "GET /languages": LANGS });
    renderApp("/login");
    expect(await screen.findByRole("heading", { name: /log in|sign in|welcome/i })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("en");
  });
});
