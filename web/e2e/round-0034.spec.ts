import { expect, test } from "@playwright/test";
import { nav, register, unique } from "./helpers";

// Runs against the stub tutor (AI_MODE=stub): "Write missing meanings" fills "(stub) meaning of <word>".
test.describe("Starter packs, remembered practice and dictation", () => {
  test("a new learner adds a pack from Home, gets meanings, reviews due words and sees progress", async ({ page }) => {
    await register(page, `round_${unique()}`);
    await expect(page.getByText("Get started in three steps")).toBeVisible();
    await page.getByRole("button", { name: "Greetings and politeness: Add 12 words" }).click();
    await expect(page.getByText(/Added 12 words/)).toBeVisible();

    await nav(page, "Vocabulary").click();
    await expect(page.getByRole("heading", { name: /\(12\)/ })).toBeVisible();
    await page.getByRole("button", { name: "Write missing meanings" }).click();
    await expect(page.getByText("(stub) meaning of hello").first()).toBeVisible();

    await nav(page, "Practice").click();
    await expect(page.getByText("Your progress")).toBeVisible();
    await page.getByRole("button", { name: "Review due words" }).click();
    for (let i = 0; i < 10; i++) {
      await page.getByRole("button", { name: "Show meaning" }).click();
      await page.getByRole("button", { name: "I knew it" }).click();
    }
    await expect(page.getByText("You knew 10 of 10")).toBeVisible();
    await page.getByRole("button", { name: "Back" }).click();

    await expect(page.getByText("1-day streak")).toBeVisible();
    const due = page.getByText("Due now").locator("xpath=following-sibling::dd");
    await expect(due).toHaveText("0");                                   // the ten answered words now rest
    await expect(page.getByText("Learning").locator("xpath=following-sibling::dd")).toHaveText("10");
  });

  test("dictation runs through to a score when the browser has a voice", async ({ page }) => {
    await register(page, `dict_${unique()}`);
    await page.getByRole("button", { name: "Food and drink: Add 12 words" }).click();
    await expect(page.getByText(/Added 12 words/)).toBeVisible();
    await nav(page, "Practice").click();
    const start = page.getByRole("button", { name: "Start dictation" });
    test.skip((await start.count()) === 0, "this browser has no read-aloud voice for English, which is the card's own message");
    await start.click();
    await page.getByLabel("Your answer").fill("definitely-wrong");
    await page.getByRole("button", { name: "Check" }).click();
    await expect(page.getByText(/Not quite. The word is/)).toBeVisible();
  });
});
