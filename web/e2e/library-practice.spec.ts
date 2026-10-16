import { expect, test } from "@playwright/test";
import { addWord, nav, register, unique } from "./helpers";

// Runs against the stub tutor (AI_MODE=stub): the story is the fixed dialogue "Hello, friend. Hello, water please. ...".
const WORDS: [string, string][] = [["hello", "a greeting"], ["friend", "someone you like"], ["water", "a drink"], ["please", "a polite word"], ["goodbye", "parting words"]];

async function learnerWithWords(page: import("@playwright/test").Page, local: string) {
  await register(page, local);
  for (const [word, meaning] of WORDS) await addWord(page, word, meaning);
}

test.describe("Story Studio, Library and Practice", () => {
  test("make a story, save it, find it in the Library, practise it, then delete it", async ({ page }) => {
    await learnerWithWords(page, `story_${unique()}`);

    await nav(page, "Studio").click();
    await page.getByRole("button", { name: "Make a story" }).click();
    await expect(page.getByRole("region", { name: "Quality report" })).toBeVisible();
    await expect(page.getByText(/Hello, friend/).first()).toBeVisible();
    await page.getByRole("button", { name: "Save to library" }).click();
    await expect(page.getByRole("button", { name: "Saved" })).toBeDisabled();

    await nav(page, "Library").click();
    await expect(page.getByText("Looks good")).toBeVisible();
    await page.getByRole("button", { name: "Open" }).click();
    await expect(page.getByRole("region", { name: "Quality report" })).toBeVisible();

    await page.getByRole("link", { name: "Practice this story" }).click();
    await expect(page).toHaveURL(/\/practice\?story=\d+/);
    await expect(page.getByText(/Sentence 1 of/)).toBeVisible();
    const choices = page.getByRole("group", { name: "Choices" }).getByRole("button");
    await choices.first().click();
    await expect(page.getByRole("status")).toBeVisible();

    await nav(page, "Library").click();
    await page.getByRole("button", { name: "Delete this story" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Delete story" }).click();
    await expect(page.getByText("No English stories saved yet")).toBeVisible();
  });

  test("flashcards run through to a score", async ({ page }) => {
    await learnerWithWords(page, `cards_${unique()}`);
    await nav(page, "Practice").click();
    await page.getByRole("button", { name: "Start flashcards" }).click();
    for (let i = 0; i < WORDS.length; i++) {
      await page.getByRole("button", { name: "Show meaning" }).click();
      await page.getByRole("button", { name: "I knew it" }).click();
    }
    await expect(page.getByText(`You knew ${WORDS.length} of ${WORDS.length}`)).toBeVisible();
  });

  test("a story saved by one learner is invisible to another", async ({ page, browser }) => {
    await learnerWithWords(page, `own_${unique()}`);
    await nav(page, "Studio").click();
    await page.getByRole("button", { name: "Make a story" }).click();
    await page.getByRole("button", { name: "Save to library" }).click();
    await expect(page.getByRole("button", { name: "Saved" })).toBeVisible();

    const other = await (await browser.newContext()).newPage();
    await register(other, `other_${unique()}`);
    await nav(other, "Library").click();
    await expect(other.getByText("No English stories saved yet")).toBeVisible();
    await other.goto("/practice?story=1");
    await expect(other.getByRole("alert")).toContainText("isn't in your library");
  });

  test("Story Studio explains how many words it needs", async ({ page }) => {
    await register(page, `few_${unique()}`);
    await addWord(page, "hello", "a greeting");
    await nav(page, "Studio").click();
    await page.getByRole("button", { name: "Make a story" }).click();
    await expect(page.getByRole("alert")).toContainText("Add at least 5 English words");
  });
});
