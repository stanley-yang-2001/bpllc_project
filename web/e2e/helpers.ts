import { expect, test, type Page } from "@playwright/test";

export const PASSWORD = "password123";
export const unique = () => Math.random().toString(36).slice(2, 8);
export const emailOf = (local: string) => `${local}@example.com`;

export async function register(page: Page, local: string, display = local) {
  await page.goto("/login");
  await page.getByRole("tab", { name: "Create account" }).click();
  await page.getByLabel("Your name").fill(display);
  await page.getByLabel("Email").fill(emailOf(local));
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("checkbox", { name: /Privacy Policy/ }).check();
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: `Welcome, ${display}` })).toBeVisible();
}

export async function login(page: Page, local: string, password = PASSWORD) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(emailOf(local));
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Log in", exact: true }).last().click();
}

export const nav = (page: Page, name: string) => page.getByRole("navigation", { name: "Main" }).getByRole("link", { name, exact: true });
export const loginButton = (page: Page) => page.getByRole("button", { name: "Log in", exact: true }).last();

/** The cell that holds a word. Its accessible name also carries the read-aloud button's label, so match the word's own text. */
export const wordCell = (page: Page, word: string) =>
  page.locator("td span[lang]").filter({ hasText: new RegExp(`^${word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`) });

export async function addWord(page: Page, word: string, meaning?: string) {
  await nav(page, "Vocabulary").click();
  await page.getByLabel("Word", { exact: true }).fill(word);
  if (meaning) await page.getByLabel("Meaning (optional)").fill(meaning);
  await page.getByRole("button", { name: "Add word" }).click();
  await expect(wordCell(page, word)).toBeVisible();
}

/** Press "Make a story" and wait for the quality report. A live story comes from Groq, which now and then answers "busy" or is slow, so one
 *  error is waited out (20 s) and tried once more before the test fails; the failure then says what the screen said. */
export async function makeStory(page: Page, attempts = 2) {
  const report = page.getByRole("region", { name: "Quality report" });
  const failed = page.getByRole("alert");
  for (let attempt = 1; ; attempt++) {
    await page.getByRole("button", { name: "Make a story" }).click();
    await expect(report.or(failed.first())).toBeVisible({ timeout: 60_000 });
    if (await report.isVisible()) return;
    const why = (await failed.first().innerText()).trim();
    if (attempt >= attempts) throw new Error(`Story Studio showed an error on each of ${attempts} tries; the last one was: ${why}`);
    test.setTimeout(test.info().timeout + 100_000);        // the retry needs its own time
    await page.waitForTimeout(20_000);
  }
}
