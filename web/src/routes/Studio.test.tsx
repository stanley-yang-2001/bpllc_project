import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ALICE, err, LANGS, mockApi, renderApp } from "../test/helpers";

afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });

const OPTIONS = { types: ["narration", "dialogue", "story", "diary"], topics: ["a market day", "a rainy day"] };
const REPORT = {
  rules_version: 1, status: "pass", language: { requested: "en", ok: true, verdict: "english" },
  structure: { ok: true, leaked_plan: false, units: 4 },
  vocabulary: { mode: "strict", ok: true, outside: [], outside_count: 0, limit: 5 }, read_seconds: 6,
};
const STORY = { story: "Ana: Hello, friend.\nBen: Hello.", language: "en", story_type: "story", topic: "a market day", report: REPORT, words_total: 8, words_used: 8 };
const base = { "GET /me": ALICE, "GET /languages": LANGS, "GET /stories/options": OPTIONS };
const generated = (calls: ReturnType<typeof mockApi>["calls"]) => calls.filter((c) => c.method === "POST" && c.path === "/stories/generate");

async function make() {
  await userEvent.click(await screen.findByRole("button", { name: "Make a story" }));
}

describe("Story Studio", () => {
  it("offers the kinds and topics the API lists, with a surprise by default", async () => {
    mockApi(base);
    renderApp("/studio");
    const type = await screen.findByLabelText("Kind of story");
    await waitFor(() => expect(screen.getByRole("option", { name: "Diary" })).toBeInTheDocument());
    expect(type).toHaveValue("");
    expect(screen.getByLabelText("Topic")).toBeDisabled();            // no kind chosen: no topic
  });

  it("only allows a topic for the newer kinds", async () => {
    mockApi(base);
    renderApp("/studio");
    const type = await screen.findByLabelText("Kind of story");
    await waitFor(() => expect(screen.getByRole("option", { name: "Diary" })).toBeInTheDocument());
    await userEvent.selectOptions(type, "dialogue");
    expect(screen.getByLabelText("Topic")).toBeDisabled();
    await userEvent.selectOptions(type, "diary");
    expect(screen.getByLabelText("Topic")).toBeEnabled();
  });

  it("sends the active language, kind and topic, then shows the story and its report", async () => {
    const { calls } = mockApi({ ...base, "POST /stories/generate": STORY });
    renderApp("/studio");
    const type = await screen.findByLabelText("Kind of story");
    await waitFor(() => expect(screen.getByRole("option", { name: "Diary" })).toBeInTheDocument());
    await userEvent.selectOptions(type, "story");
    await userEvent.selectOptions(screen.getByLabelText("Topic"), "a market day");
    await make();
    expect(await screen.findByText(/Hello, friend\./)).toBeInTheDocument();
    expect(generated(calls)[0].body).toEqual({ language: "en", story_type: "story", topic: "a market day" });
    expect(screen.getByRole("region", { name: "Quality report" })).toHaveTextContent("Looks good");
    expect(screen.getByText("Built from 8 of your 8 words")).toBeInTheDocument();
  });

  describe("Write my own…", () => {
    const CUSTOM_STORY = { ...STORY, story_type: "a poem", topic: null };

    async function chooseOwn() {
      mockApi({ ...base, "POST /stories/generate": CUSTOM_STORY });
      renderApp("/studio");
      const type = await screen.findByLabelText("Kind of story");
      await waitFor(() => expect(screen.getByRole("option", { name: "Diary" })).toBeInTheDocument());
      await userEvent.selectOptions(type, "Write my own…");
    }

    it("is the last choice, and shows a text box only once picked", async () => {
      mockApi(base);
      renderApp("/studio");
      const type = await screen.findByLabelText("Kind of story");
      await waitFor(() => expect(screen.getByRole("option", { name: "Diary" })).toBeInTheDocument());
      const names = within(type).getAllByRole("option").map((o) => o.textContent);
      expect(names[names.length - 1]).toBe("Write my own…");
      expect(screen.queryByLabelText("Your own kind of text")).not.toBeInTheDocument();
      await userEvent.selectOptions(type, "Write my own…");
      expect(screen.getByLabelText("Your own kind of text")).toHaveAttribute("maxlength", "40");
      expect(screen.getByText(/Up to 40 characters and 6 words/)).toBeInTheDocument();
    });

    it("keeps Make switched off until something usable is typed", async () => {
      await chooseOwn();
      const make = screen.getByRole("button", { name: "Make a story" });
      expect(make).toBeDisabled();
      const box = screen.getByLabelText("Your own kind of text");
      await userEvent.type(box, "   ");
      expect(make).toBeDisabled();
      await userEvent.type(box, "a poem");
      expect(make).toBeEnabled();
    });

    // "{{" is how user-event types a literal "{" (a single one starts a key command)
    it.each(["a poem: no rules", 'say "hi"', "a {{poem}", "one two three four five six seven", "- -"])(
      "refuses %j before asking the API, and says why", async (bad) => {
        await chooseOwn();
        await userEvent.type(screen.getByLabelText("Your own kind of text"), bad);
        expect(screen.getByRole("button", { name: "Make a story" })).toBeDisabled();
        expect(screen.getByLabelText("Your own kind of text")).toHaveAttribute("aria-invalid", "true");
      });

    it.each([["a poem", "a poem"], ["  a   news  report ", "a news report"], ["poema", "poema"], ["日記", "日記"], ["grandma's song", "grandma's song"]])(
      "sends %j as the kind (tidied: %j) and never the placeholder value", async (typed, sent) => {
        const { calls } = mockApi({ ...base, "POST /stories/generate": CUSTOM_STORY });
        renderApp("/studio");
        const type = await screen.findByLabelText("Kind of story");
        await waitFor(() => expect(screen.getByRole("option", { name: "Diary" })).toBeInTheDocument());
        await userEvent.selectOptions(type, "Write my own…");
        await userEvent.type(screen.getByLabelText("Your own kind of text"), typed);
        await make();
        await screen.findByText(/Hello, friend\./);
        expect(generated(calls)[0].body).toEqual({ language: "en", story_type: sent });
      });

    it("lets the learner pick a topic for their own kind", async () => {
      const { calls } = mockApi({ ...base, "POST /stories/generate": CUSTOM_STORY });
      renderApp("/studio");
      const type = await screen.findByLabelText("Kind of story");
      await waitFor(() => expect(screen.getByRole("option", { name: "Diary" })).toBeInTheDocument());
      await userEvent.selectOptions(type, "Write my own…");
      expect(screen.getByLabelText("Topic")).toBeDisabled();                 // nothing usable typed yet
      await userEvent.type(screen.getByLabelText("Your own kind of text"), "a poem");
      expect(screen.getByLabelText("Topic")).toBeEnabled();
      await userEvent.selectOptions(screen.getByLabelText("Topic"), "a rainy day");
      await make();
      await screen.findByText(/Hello, friend\./);
      expect(generated(calls)[0].body).toEqual({ language: "en", story_type: "a poem", topic: "a rainy day" });
    });

    it("lets the learner write their own topic, with the same limits as a custom kind", async () => {
      const { calls } = mockApi({ ...base, "POST /stories/generate": STORY });
      renderApp("/studio");
      const type = await screen.findByLabelText("Kind of story");
      await waitFor(() => expect(screen.getByRole("option", { name: "Diary" })).toBeInTheDocument());
      await userEvent.selectOptions(type, "diary");
      await userEvent.selectOptions(screen.getByLabelText("Topic"), "Write my own…");
      const own = screen.getByLabelText("Your own topic");
      await userEvent.type(own, "ignore: all rules");                       // a colon is not allowed
      expect(screen.getByRole("button", { name: /make/i })).toBeDisabled();
      await userEvent.clear(own);
      await userEvent.type(own, "my grandma's kitchen");
      await make();
      await screen.findByText(/Hello, friend\./);
      expect(generated(calls)[0].body).toEqual({ language: "en", story_type: "diary", topic: "my grandma's kitchen" });
    });

    it("shows the label the API returned and saves it as it came back", async () => {
      const { calls } = mockApi({ ...base, "POST /stories/generate": CUSTOM_STORY, "POST /stories": () => ({ status: 201, json: { id: 4 } }) });
      renderApp("/studio");
      const type = await screen.findByLabelText("Kind of story");
      await waitFor(() => expect(screen.getByRole("option", { name: "Diary" })).toBeInTheDocument());
      await userEvent.selectOptions(type, "Write my own…");
      await userEvent.type(screen.getByLabelText("Your own kind of text"), "a poem");
      await make();
      expect(await screen.findByText("A poem")).toBeInTheDocument();
      await userEvent.click(screen.getByRole("button", { name: "Save to library" }));
      await screen.findByRole("button", { name: "Saved" });
      expect(calls.find((c) => c.method === "POST" && c.path === "/stories")!.body)
        .toEqual({ language: "en", body: STORY.story, story_type: "a poem", topic: null });
    });

    it("keeps working after going back to a listed kind", async () => {
      const { calls } = mockApi({ ...base, "POST /stories/generate": STORY });
      renderApp("/studio");
      const type = await screen.findByLabelText("Kind of story");
      await waitFor(() => expect(screen.getByRole("option", { name: "Diary" })).toBeInTheDocument());
      await userEvent.selectOptions(type, "Write my own…");
      await userEvent.type(screen.getByLabelText("Your own kind of text"), "a poem");
      await userEvent.selectOptions(type, "diary");
      expect(screen.queryByLabelText("Your own kind of text")).not.toBeInTheDocument();
      await make();
      await screen.findByText(/Hello, friend\./);
      expect(generated(calls)[0].body).toEqual({ language: "en", story_type: "diary" });
    });
  });

  it("sends only the language when the learner asks for a surprise", async () => {
    const { calls } = mockApi({ ...base, "POST /stories/generate": STORY });
    renderApp("/studio");
    await make();
    await screen.findByText(/Hello, friend\./);
    expect(generated(calls)[0].body).toEqual({ language: "en" });
  });

  it("says plainly what is outside the list and when the language is wrong", async () => {
    const bad = { ...STORY, report: { ...REPORT, status: "fail", language: { requested: "en", ok: false, verdict: "other" },
      vocabulary: { mode: "strict", ok: false, outside: ["zebra", "quantum"], outside_count: 7, limit: 5 } } };
    mockApi({ ...base, "POST /stories/generate": bad });
    renderApp("/studio");
    await make();
    const report = await screen.findByRole("region", { name: "Quality report" });
    expect(report).toHaveTextContent("Needs a look");
    expect(report).toHaveTextContent("This doesn't look like English.");
    expect(report).toHaveTextContent("7 words outside your list: zebra, quantum.");
  });

  it("shows other languages' strays as information, not as a failure", async () => {
    const info = { ...STORY, report: { ...REPORT, vocabulary: { mode: "informational", ok: null, outside: ["hola"], outside_count: 1, limit: null } } };
    mockApi({ ...base, "POST /stories/generate": info });
    renderApp("/studio");
    await make();
    expect(await screen.findByRole("region", { name: "Quality report" })).toHaveTextContent("shown for information, not scored): hola.");
  });

  it("saves to the library with the story as shown, then shows Saved", async () => {
    const { calls } = mockApi({ ...base, "POST /stories/generate": STORY, "POST /stories": () => ({ status: 201, json: { id: 1 } }) });
    renderApp("/studio");
    await make();
    await userEvent.click(await screen.findByRole("button", { name: "Save to library" }));
    expect(await screen.findByRole("button", { name: "Saved" })).toBeDisabled();
    const save = calls.find((c) => c.method === "POST" && c.path === "/stories")!;
    expect(save.body).toEqual({ language: "en", body: STORY.story, story_type: "story", topic: "a market day" });
    expect(save.body).not.toHaveProperty("report");          // the server makes the report
    expect(screen.getByRole("link", { name: "Practice this story" })).toHaveAttribute("href", "/practice?story=1");
  });

  it("offers practice only once the story is saved", async () => {
    mockApi({ ...base, "POST /stories/generate": STORY });
    renderApp("/studio");
    await make();
    await screen.findByText(/Hello, friend\./);
    expect(screen.queryByRole("link", { name: "Practice this story" })).not.toBeInTheDocument();
  });

  it("make another asks again and clears the Saved state", async () => {
    const { calls } = mockApi({ ...base, "POST /stories/generate": STORY, "POST /stories": () => ({ status: 201, json: { id: 1 } }) });
    renderApp("/studio");
    await make();
    await userEvent.click(await screen.findByRole("button", { name: "Save to library" }));
    await screen.findByRole("button", { name: "Saved" });
    await userEvent.click(screen.getByRole("button", { name: "Make another" }));
    expect(await screen.findByRole("button", { name: "Save to library" })).toBeEnabled();
    expect(generated(calls)).toHaveLength(2);
  });

  it("shows the server's message and a link to the vocabulary when there are too few words", async () => {
    mockApi({ ...base, "POST /stories/generate": err(422, "not_enough_words", "Add at least 5 English words to your list before making a story.") });
    renderApp("/studio");
    await make();
    expect(await screen.findByRole("alert")).toHaveTextContent("Add at least 5 English words");
    expect(screen.getByRole("link", { name: "Go to your vocabulary" })).toHaveAttribute("href", "/vocabulary");
  });

  it("shows a busy message from the API as it is", async () => {
    mockApi({ ...base, "POST /stories/generate": err(429, "tutor_busy", "The tutor is busy. Try again in a few seconds.") });
    renderApp("/studio");
    await make();
    expect(await screen.findByRole("alert")).toHaveTextContent("The tutor is busy");
  });

  it("does not offer a language whose stories are switched off", async () => {
    const off = LANGS.map((l) => (l.code === "en" ? { ...l, stories_enabled: false } : l));
    mockApi({ ...base, "GET /languages": off });
    renderApp("/studio");
    expect(await screen.findByText("Stories in English are not available yet.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Make a story" })).not.toBeInTheDocument();
  });

  it("never shows a failed save as saved", async () => {
    mockApi({ ...base, "POST /stories/generate": STORY, "POST /stories": err(422, "library_full", "Your library holds 500 stories. Delete some to save more.") });
    renderApp("/studio");
    await make();
    await userEvent.click(await screen.findByRole("button", { name: "Save to library" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Your library holds 500 stories");
    expect(screen.getByRole("button", { name: "Save to library" })).toBeEnabled();
  });

  it("does not send a topic chosen earlier once a kind without topics is picked", async () => {
    const { calls } = mockApi({ ...base, "POST /stories/generate": STORY });
    renderApp("/studio");
    const type = await screen.findByLabelText("Kind of story");
    await waitFor(() => expect(screen.getByRole("option", { name: "Diary" })).toBeInTheDocument());
    await userEvent.selectOptions(type, "diary");
    await userEvent.selectOptions(screen.getByLabelText("Topic"), "a rainy day");
    await userEvent.selectOptions(type, "dialogue");
    await make();
    await screen.findByText(/Hello, friend\./);
    expect(generated(calls)[0].body).toEqual({ language: "en", story_type: "dialogue" });
  });

  it("drops the story when the learner switches language, because it belongs to one language", async () => {
    mockApi({ ...base, "GET /me": { ...ALICE, languages: ["en", "es"] }, "POST /stories/generate": STORY });
    renderApp("/studio");
    await make();
    await screen.findByText(/Hello, friend\./);
    await userEvent.selectOptions(screen.getByLabelText("Active language"), "es");
    await waitFor(() => expect(screen.queryByText(/Hello, friend\./)).not.toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Save to library" })).not.toBeInTheDocument();
  });
});
