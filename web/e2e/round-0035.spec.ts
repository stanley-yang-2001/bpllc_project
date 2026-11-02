import { expect, test } from "@playwright/test";
import { nav, register, unique } from "./helpers";

// Runs against the stub tutor (every word "noun") or the live one (the model's own labels, "interjection" for hello), so it only asks that
// the word got a label.
test("a learner labels words with the tutor and practises parts of speech", async ({ page }) => {
  await register(page, `pos_${unique()}`);
  await page.getByRole("button", { name: "Greetings and politeness: Add 12 words" }).click();
  await expect(page.getByText(/Added 12 words/)).toBeVisible();

  await nav(page, "Practice").click();
  await page.getByRole("button", { name: "Start parts of speech" }).click();
  await expect(page.getByText("No labelled words yet")).toBeVisible();     // nothing is labelled yet

  await nav(page, "Vocabulary").click();
  await page.getByRole("button", { name: "Label parts of speech" }).click();
  await expect(page.getByText("The tutor labelled 12 words.")).toBeVisible();
  await expect(page.getByLabel("Part of speech of hello")).toHaveValue(/.+/);

  await nav(page, "Practice").click();
  await page.getByRole("button", { name: "Start parts of speech" }).click();
  await expect(page.getByText("What kind of word is this?")).toBeVisible();
  await page.getByRole("button", { name: "noun", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: /./ }).first()).toBeVisible();
});
