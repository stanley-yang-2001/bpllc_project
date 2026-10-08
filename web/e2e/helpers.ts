import { expect, type Page } from "@playwright/test";

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

export async function addWord(page: Page, word: string, meaning?: string) {
  await nav(page, "Vocabulary").click();
  await page.getByLabel("Word", { exact: true }).fill(word);
  if (meaning) await page.getByLabel("Meaning (optional)").fill(meaning);
  await page.getByRole("button", { name: "Add word" }).click();
  await expect(page.getByRole("cell", { name: word, exact: true })).toBeVisible();
}
