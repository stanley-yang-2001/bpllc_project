import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ALICE, err, LANGS, mockApi, renderApp } from "../test/helpers";

afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });

const card = (id: number, over: Record<string, unknown> = {}) => ({
  id, language: "en", story_type: "dialogue", topic: null, body: `Ana: Hello ${id}.\nBen: Hi.`, passed: true, created_at: "2026-10-16T10:00:00Z", ...over,
});
const REPORT = { status: "pass", language: { ok: true }, structure: { ok: true }, vocabulary: { mode: "strict", ok: true, outside: [], outside_count: 0, limit: 5 }, read_seconds: 5 };
const page = (items: unknown[], total = items.length, offset = 0) => ({ items, total, limit: 10, offset });
const base = { "GET /me": ALICE, "GET /languages": LANGS };
const listCalls = (calls: ReturnType<typeof mockApi>["calls"]) => calls.filter((c) => c.method === "GET" && c.path.startsWith("/stories?"));

describe("library page", () => {
  it("lists this language's stories newest first, with type, topic and a verdict", async () => {
    const { calls } = mockApi({ ...base, "GET /stories": page([card(2, { story_type: "diary", topic: "a rainy day", passed: false }), card(1)]) });
    renderApp("/library");
    expect(await screen.findByText("Diary")).toBeInTheDocument();
    expect(screen.getByText("A rainy day")).toBeInTheDocument();
    expect(screen.getByText("Needs a look")).toBeInTheDocument();
    expect(screen.getByText("Looks good")).toBeInTheDocument();
    expect(listCalls(calls)[0].path).toBe("/stories?language=en&limit=10&offset=0");
  });

  it("calls a chat story what it is", async () => {
    mockApi({ ...base, "GET /stories": page([card(1, { story_type: null })]) });
    renderApp("/library");
    expect(await screen.findByText("From chat")).toBeInTheDocument();
  });

  it("explains an empty library and points to Story Studio", async () => {
    mockApi({ ...base, "GET /stories": page([]) });
    renderApp("/library");
    expect(await screen.findByText("No English stories saved yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Make a story in Story Studio" })).toHaveAttribute("href", "/studio");
  });

  it("opens a story to show its whole text and report, and closes it again", async () => {
    const { calls } = mockApi({ ...base, "GET /stories": page([card(1)]), "GET /stories/1": { ...card(1), body: "Ana: Hello there.\nBen: Hi, friend.", report: REPORT } });
    renderApp("/library");
    await userEvent.click(await screen.findByRole("button", { name: "Open" }));
    expect(await screen.findByText(/Hi, friend\./)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Quality report" })).toHaveTextContent("Looks good");
    expect(calls.filter((c) => c.path === "/stories/1")).toHaveLength(1);
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    await waitFor(() => expect(screen.queryByRole("region", { name: "Quality report" })).not.toBeInTheDocument());
  });

  it("links each story to practice for that story", async () => {
    mockApi({ ...base, "GET /stories": page([card(7)]) });
    renderApp("/library");
    expect(await screen.findByRole("link", { name: "Practice this story" })).toHaveAttribute("href", "/practice?story=7");
  });

  it("deletes only after the learner confirms, then refreshes the list", async () => {
    let gone = false;
    const { calls } = mockApi({
      ...base,
      "GET /stories": () => ({ json: page(gone ? [] : [card(1)]) }),
      "DELETE /stories/1": () => { gone = true; return { status: 204 }; },
    });
    renderApp("/library");
    await userEvent.click(await screen.findByRole("button", { name: "Delete this story" }));
    const dialog = within(await screen.findByRole("dialog"));
    await userEvent.click(dialog.getByRole("button", { name: "Cancel" }));
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
    await userEvent.click(screen.getByRole("button", { name: "Delete this story" }));
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Delete story" }));
    expect(await screen.findByText("No English stories saved yet")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "DELETE")).toHaveLength(1);
  });

  it("shows the server's message when a delete fails and keeps the story", async () => {
    mockApi({ ...base, "GET /stories": page([card(1)]), "DELETE /stories/1": err(404, "not_found", "That story isn't in your library.") });
    renderApp("/library");
    await userEvent.click(await screen.findByRole("button", { name: "Delete this story" }));
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Delete story" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("That story isn't in your library.");
    expect(screen.getByText(/Hello 1\./)).toBeInTheDocument();
  });

  it("pages ten at a time", async () => {
    const { calls } = mockApi({
      ...base,
      "GET /stories": ({ path }: { path: string }) => ({ json: path.includes("offset=10") ? page([card(11)], 11, 10) : page(Array.from({ length: 10 }, (_, i) => card(20 - i)), 11, 0) }),
    });
    renderApp("/library");
    expect(await screen.findByText("1–10 of 11")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Previous/ })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: /Next/ }));
    expect(await screen.findByText("11–11 of 11")).toBeInTheDocument();
    expect(listCalls(calls).some((c) => c.path.includes("offset=10"))).toBe(true);
    expect(screen.getByRole("button", { name: /Next/ })).toBeDisabled();
  });

  it("asks for the other language's stories after a switch, from the first page", async () => {
    const { calls } = mockApi({ ...base, "GET /me": { ...ALICE, languages: ["en", "es"] }, "GET /stories": page([card(1)]) });
    renderApp("/library");
    await screen.findByText(/Hello 1\./);
    await userEvent.selectOptions(screen.getByLabelText("Active language"), "es");
    await waitFor(() => expect(listCalls(calls).some((c) => c.path === "/stories?language=es&limit=10&offset=0")).toBe(true));
  });

  it("shows an error from the list instead of an empty library", async () => {
    mockApi({ ...base, "GET /stories": err(500, "internal_error", "Something went wrong. Please try again.") });
    renderApp("/library");
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");
    expect(screen.queryByText(/No English stories/)).not.toBeInTheDocument();
  });

  it("goes back to the first page when the language changes", async () => {
    const { calls } = mockApi({
      ...base, "GET /me": { ...ALICE, languages: ["en", "es"] },
      "GET /stories": ({ path }: { path: string }) => ({ json: path.includes("offset=10") ? page([card(11)], 11, 10) : page(Array.from({ length: 10 }, (_, i) => card(20 - i)), 11, 0) }),
    });
    renderApp("/library");
    await userEvent.click(await screen.findByRole("button", { name: /Next/ }));
    await screen.findByText("11–11 of 11");
    await userEvent.selectOptions(screen.getByLabelText("Active language"), "es");
    await waitFor(() => expect(listCalls(calls).some((c) => c.path === "/stories?language=es&limit=10&offset=0")).toBe(true));
    expect(listCalls(calls).some((c) => c.path.startsWith("/stories?language=es") && c.path.includes("offset=10"))).toBe(false);
  });
});
