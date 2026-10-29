import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ALICE, err, LANGS, mockApi, renderApp } from "../test/helpers";

afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });

const PACKS = { items: [{ id: "basics", total: 12, remaining: 12 }, { id: "food", total: 12, remaining: 5 }, { id: "people", total: 12, remaining: 0 }, { id: "numbers", total: 12, remaining: 12 }], gloss_available: true };
const WORDS = (total: number) => ({ items: [], total, limit: 1, offset: 0 });
const base = { "GET /me": ALICE, "GET /languages": LANGS, "GET /words/starter-packs": PACKS };

describe("first-run guide on Home", () => {
  it("shows three steps and the starter packs to someone with no words", async () => {
    mockApi({ ...base, "GET /words": WORDS(0) });
    renderApp("/");
    expect(await screen.findByText("Get started in three steps")).toBeInTheDocument();
    expect(screen.getByText("1. Add some words")).toBeInTheDocument();
    expect(await screen.findByText("Greetings and politeness")).toBeInTheDocument();
  });

  it("is not shown once the learner has words", async () => {
    mockApi({ ...base, "GET /words": WORDS(7) });
    renderApp("/");
    expect(await screen.findByText("7")).toBeInTheDocument();
    expect(screen.queryByText("Get started in three steps")).not.toBeInTheDocument();
  });

  it("stays up after a pack is added, so the learner sees what happened", async () => {
    let total = 0;
    const { calls } = mockApi({ ...base, "GET /words": () => ({ json: WORDS(total) }),
      "POST /words/starter-packs": () => { total = 12; return { json: { added: 12, duplicates: 0, with_meaning: false } }; } });
    renderApp("/");
    await userEvent.click(await screen.findByRole("button", { name: "Greetings and politeness: Add 12 words" }));
    expect(await screen.findByText(/Added 12 words. They have no meanings yet/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to Vocabulary" })).toHaveAttribute("href", "/vocabulary");
    expect(calls.find((c) => c.method === "POST" && c.path === "/words/starter-packs")!.body).toEqual({ language: "en", pack: "basics" });
    await waitFor(() => expect(screen.getByText("Get started in three steps")).toBeInTheDocument());
  });
});

describe("starter packs", () => {
  it("shows how many words each pack would add, and ticks a pack that is complete", async () => {
    mockApi({ ...base, "GET /words": WORDS(0) });
    renderApp("/");
    expect(await screen.findByRole("button", { name: "Food and drink: Add 5 words" })).toBeInTheDocument();
    const people = screen.getByText("People and places").closest("li")!;
    expect(within(people).getByText("All added")).toBeInTheDocument();
    expect(within(people).queryByRole("button")).not.toBeInTheDocument();
  });

  it("says the words came with English meanings when they did", async () => {
    mockApi({ ...base, "GET /words": WORDS(0), "POST /words/starter-packs": { added: 12, duplicates: 0, with_meaning: true } });
    renderApp("/");
    await userEvent.click(await screen.findByRole("button", { name: "Greetings and politeness: Add 12 words" }));
    expect(await screen.findByText("Added 12 words, each with a short English meaning.")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Go to Vocabulary" })).not.toBeInTheDocument();
  });

  it("says when there was nothing new", async () => {
    mockApi({ ...base, "GET /words": WORDS(0), "POST /words/starter-packs": { added: 0, duplicates: 12, with_meaning: true } });
    renderApp("/");
    await userEvent.click(await screen.findByRole("button", { name: "Greetings and politeness: Add 12 words" }));
    expect(await screen.findByText("Nothing new to add: you already have these words.")).toBeInTheDocument();
  });

  it("shows the server's reason when adding fails", async () => {
    mockApi({ ...base, "GET /words": WORDS(0), "POST /words/starter-packs": err(404, "not_found", "That pack isn't available for this language.") });
    renderApp("/");
    await userEvent.click(await screen.findByRole("button", { name: "Greetings and politeness: Add 12 words" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("That pack isn't available");
  });

  it("is simply left out when the packs cannot be loaded", async () => {
    mockApi({ "GET /me": ALICE, "GET /languages": LANGS, "GET /words": WORDS(0), "GET /words/starter-packs": err(500, "internal", "boom") });
    renderApp("/");
    expect(await screen.findByText("Get started in three steps")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("Starter word packs")).not.toBeInTheDocument());
  });

  it("is offered on the Vocabulary page while the list is short, and not once it is long", async () => {
    const page = (total: number) => ({ items: [], total, limit: 50, offset: 0 });
    mockApi({ ...base, "GET /words": page(3), "GET /sets": { items: [] } });
    const { ui } = renderApp("/vocabulary");
    expect(await screen.findByText("Starter word packs")).toBeInTheDocument();
    ui.unmount();
    mockApi({ ...base, "GET /words": page(80), "GET /sets": { items: [] } });
    renderApp("/vocabulary");
    await screen.findByText(/\(80\)/);
    expect(screen.queryByText("Starter word packs")).not.toBeInTheDocument();
  });
});
