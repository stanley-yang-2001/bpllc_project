import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ALICE, err, LANGS, mockApi, renderApp } from "../test/helpers";

afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); });

const W = (id: number, word: string, meaning: string | null = null) => ({ id, language: "en", word, meaning, created_at: "2026-01-01T00:00:00Z" });
const page = (items: ReturnType<typeof W>[], total = items.length) => ({ items, total, limit: 50, offset: 0 });
const base = { "GET /me": ALICE, "GET /languages": LANGS };

describe("vocabulary page", () => {
  it("lists words with their meanings and shows the total", async () => {
    mockApi({ ...base, "GET /words": page([W(1, "bread", "pan"), W(2, "water")]) });
    renderApp("/vocabulary");
    expect(await screen.findByText("bread")).toBeInTheDocument();
    expect(screen.getByText("pan")).toBeInTheDocument();
    expect(screen.getByText("(2)")).toBeInTheDocument();
  });

  it("shows an empty state with the next action", async () => {
    mockApi({ ...base, "GET /words": page([]) });
    renderApp("/vocabulary");
    expect(await screen.findByText(/No words yet/)).toBeInTheDocument();
  });

  it("surfaces a server error from adding a duplicate, and does not clear the input", async () => {
    mockApi({ ...base, "GET /words": page([W(1, "bread")]), "POST /words": err(409, "conflict", "'bread' is already in your list.") });
    renderApp("/vocabulary");
    await screen.findByText("bread");
    await userEvent.type(screen.getByLabelText("Word"), "bread");
    await userEvent.click(screen.getByRole("button", { name: "Add word" }));
    expect(await screen.findByText("'bread' is already in your list.")).toBeInTheDocument();
    expect(screen.getByLabelText("Word")).toHaveValue("bread");
  });

  it("adds a word for the active language and refetches (not optimistic)", async () => {
    let words = [W(1, "bread")];
    const { calls } = mockApi({
      ...base,
      "GET /words": () => ({ json: page(words) }),
      "POST /words": ({ body }: { body: { word: string } }) => { words = [W(2, body.word.toLowerCase()), ...words]; return { status: 201, json: words[0] }; },
    });
    renderApp("/vocabulary");
    await screen.findByText("bread");
    await userEvent.type(screen.getByLabelText("Word"), "Water");
    await userEvent.type(screen.getByLabelText("Meaning (optional)"), "agua");
    await userEvent.click(screen.getByRole("button", { name: "Add word" }));
    expect(await screen.findByText("water")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST" && c.path === "/words")!.body).toEqual({ language: "en", word: "Water", meaning: "agua" });
    expect(screen.getByLabelText("Word")).toHaveValue("");
  });

  it("deletes the selected words immediately and restores them if the server fails", async () => {
    mockApi({ ...base, "GET /words": page([W(1, "bread"), W(2, "water")]), "POST /words/delete": err(500, "internal_error", "Something went wrong.") });
    renderApp("/vocabulary");
    await userEvent.click(await screen.findByLabelText("Select bread"));
    await userEvent.click(screen.getByRole("button", { name: /Delete selected/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Delete word" }));          // the styled confirmation
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Something went wrong."));
    expect(await screen.findByText("bread")).toBeInTheDocument();   // rolled back
  });

  it("cancelling the confirmation deletes nothing (button and backdrop)", async () => {
    const { calls } = mockApi({ ...base, "GET /words": page([W(1, "bread"), W(2, "water")]), "POST /words/delete": { deleted: 2 } });
    renderApp("/vocabulary");
    await userEvent.click(await screen.findByLabelText("Select all on this page"));
    await userEvent.click(screen.getByRole("button", { name: /Delete selected/ }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Delete 2 words?")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toHaveFocus();          // the safe choice is the default

    await userEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Delete selected/ }));        // open again, dismiss via the backdrop
    await userEvent.click(await screen.findByRole("dialog"));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

    expect(calls.some((c) => c.path === "/words/delete")).toBe(false);
    expect(screen.getByText("bread")).toBeInTheDocument();
    expect(screen.getByText("2 selected")).toBeInTheDocument();                            // selection kept so you can still change your mind
  });

  it("edits a meaning inline and saves on Enter", async () => {
    const { calls } = mockApi({ ...base, "GET /words": page([W(1, "bread")]), "PATCH /words/1": () => ({ json: W(1, "bread", "pan") }) });
    renderApp("/vocabulary");
    await userEvent.click(await screen.findByRole("button", { name: "Edit meaning of bread" }));
    await userEvent.type(screen.getByLabelText("Meaning of bread"), "pan{Enter}");
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH")!.body).toEqual({ meaning: "pan" }));
  });

  it("shows the CSV upload result including invalid rows", async () => {
    mockApi({
      ...base, "GET /words": page([]),
      "POST /words/upload": { added: 3, duplicates: 1, invalid_count: 1, invalid: [{ row: 5, reason: "Words may contain only letters, apostrophes, hyphens and spaces." }] },
    });
    renderApp("/vocabulary");
    await screen.findByText(/No words yet/);
    await userEvent.upload(screen.getByLabelText("CSV file"), new File(["word\nx\n"], "w.csv", { type: "text/csv" }));
    const status = await screen.findByText(/Added 3, duplicates 1, invalid 1/);
    expect(within(status.closest("[role=status]") as HTMLElement).getByText(/Row 5/)).toBeInTheDocument();
  });

  it("adds a new language and switches to it", async () => {
    mockApi({ ...base, "GET /words": page([]), "POST /me/languages": { ...ALICE, languages: ["en", "es"] } });
    renderApp("/vocabulary");
    await screen.findByText(/No words yet/);
    await userEvent.selectOptions(screen.getByLabelText("Language to start"), "es");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    await waitFor(() => expect(screen.getByLabelText("Active language")).toHaveValue("es"));
    expect(localStorage.getItem("tutor:lang:1")).toBe("es");
  });
});
