import { expect, test } from "@playwright/test";
import { addWord, nav, register, unique } from "./helpers";

// Runs against the stub tutor (AI_MODE=stub). Covers the newer controls: the kind-of-story picker with a kind of your own,
// the topic picker, and the User ID row in Settings.
const WORDS: [string, string][] = [["hello", "a greeting"], ["friend", "someone you like"], ["water", "a drink"], ["please", "a polite word"], ["goodbye", "parting words"]];

async function learnerWithWords(page: import("@playwright/test").Page, local: string) {
  await register(page, local);
  for (const [word, meaning] of WORDS) await addWord(page, word, meaning);
}

test.describe("Story Studio options and Settings", () => {
  test("a kind of your own: a bad label blocks Make, a good one makes a story", async ({ page }) => {
    await learnerWithWords(page, `kind_${unique()}`);
    await nav(page, "Studio").click();
    await page.getByLabel("Kind of story").selectOption({ label: "Write my own…" });

    const make = page.getByRole("button", { name: "Make a story" });
    const own = page.getByLabel("Your own kind of text");
    await own.fill("this label has far too many words in it");
    await expect(make).toBeDisabled();
    await own.fill("a poem");
    await expect(make).toBeEnabled();

    await make.click();
    await expect(page.getByRole("region", { name: "Quality report" })).toBeVisible();
    await expect(page.getByText(/Hello, friend/).first()).toBeVisible();
  });

  test("the topic hint shows for the classic styles and goes away for a newer kind", async ({ page }) => {
    await learnerWithWords(page, `topic_${unique()}`);
    await nav(page, "Studio").click();
    const hint = page.getByText(/Topics are for the newer kinds of story/);
    await expect(hint).toBeVisible();                       // "Surprise me" can still pick a classic style
    await page.getByLabel("Kind of story").selectOption({ label: "Write my own…" });
    await page.getByLabel("Your own kind of text").fill("a diary");
    await expect(hint).toBeHidden();
    await page.getByLabel("Topic").selectOption({ index: 1 });
    await page.getByRole("button", { name: "Make a story" }).click();
    await expect(page.getByRole("region", { name: "Quality report" })).toBeVisible();
  });

  test("Settings shows the learner's own User ID in the Account card", async ({ page }) => {
    await register(page, `uid_${unique()}`);
    await nav(page, "Settings").click();
    const id = page.getByTestId("user-id");
    await expect(id).toBeVisible();
    await expect(id).toHaveText(/^\d+$/);
    await expect(page.getByText("User ID")).toBeVisible();
    await expect(page.getByRole("button", { name: /copy/i })).toHaveCount(0);       // no copy button, by design
  });
});
