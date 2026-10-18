import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { ALICE, mockApi, renderApp } from "../test/helpers";

const LANGS = [
  { code: "en", name: "English", native: "English", tier: 1, stories_enabled: true },
  { code: "es", name: "Spanish", native: "Español", tier: 1, stories_enabled: true },
  { code: "zh", name: "Chinese (Simplified)", native: "中文简体", tier: 2, stories_enabled: false },
  { code: "ja", name: "Japanese", native: "日本語", tier: 2, stories_enabled: true },
];

afterEach(() => localStorage.clear());

describe("languages are shown in their own names (M8a)", () => {
  it("the header picker lists each studied language by its own name and marks it with lang", async () => {
    mockApi({ "GET /me": { ...ALICE, languages: ["en", "es", "zh"] }, "GET /languages": LANGS });
    renderApp("/");
    const picker = await screen.findByLabelText("Active language");
    await waitFor(() => expect(within(picker).getAllByRole("option")).toHaveLength(3));
    const options = within(picker).getAllByRole("option");
    expect(options.map((o) => o.textContent)).toEqual(["English", "Español", "中文简体"]);
    expect(options.map((o) => o.getAttribute("lang"))).toEqual(["en", "es", "zh"]);
    expect(within(picker).queryByRole("option", { name: "Chinese (Simplified)" })).toBeNull();
  });

  it("the page heading uses the native name, inside an element carrying lang", async () => {
    mockApi({ "GET /me": { ...ALICE, languages: ["ja"] }, "GET /languages": LANGS, "GET /words": { items: [], total: 0 } });
    renderApp("/vocabulary");
    const name = await screen.findByText("日本語", { selector: "span" });
    expect(name).toHaveAttribute("lang", "ja");
  });

  it("the language a learner can start next is also listed by its own name", async () => {
    mockApi({ "GET /me": { ...ALICE, languages: ["en"] }, "GET /languages": LANGS, "GET /words": { items: [], total: 0 } });
    renderApp("/vocabulary");
    const select = await screen.findByLabelText("Language to start");
    await waitFor(() => expect(within(select).getAllByRole("option").map((o) => o.textContent)).toEqual(["Study another language…", "Español", "中文简体", "日本語"]));
    await userEvent.selectOptions(select, "zh");
  });
});
