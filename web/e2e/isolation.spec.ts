import { expect, test, type Browser, type Page } from "@playwright/test";

/** Real browser, real nginx + API + database. These are the "user B must never see user A" scenarios. */

const unique = () => Math.random().toString(36).slice(2, 8);
const PASSWORD = "password123";

async function register(page: Page, username: string, display = username) {
  await page.goto("/login");
  await page.getByRole("tab", { name: "Create account" }).click();
  await page.getByLabel("Your name").fill(display);
  await page.getByLabel("Email").fill(`${username}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("checkbox", { name: /Privacy Policy/ }).check();
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: `Welcome, ${display}` })).toBeVisible();
}

async function login(page: Page, username: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(`${username}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Log in", exact: true }).last().click();
  await expect(page.getByRole("heading", { name: /^Welcome,/ })).toBeVisible();
}

async function addWord(page: Page, word: string) {
  await nav(page, "Vocabulary").click();
  await page.getByLabel("Word", { exact: true }).fill(word);
  await page.getByRole("button", { name: "Add word" }).click();
  await expect(page.getByRole("cell", { name: word, exact: true })).toBeVisible();
}

/** The top navigation only (the Home page also has cards linking to the same places). */
const nav = (page: Page, name: string) => page.getByRole("navigation", { name: "Main" }).getByRole("link", { name, exact: true });

const logout = (page: Page) => page.getByRole("button", { name: "Log out", exact: true }).click();

async function newUser(browser: Browser, username: string) {
  const context = await browser.newContext();
  const page = await context.newPage();
  await register(page, username);
  return { context, page };
}

test.describe("two people, two browsers", () => {
  test("B cannot see or touch A's words", async ({ browser }) => {
    const a = await newUser(browser, `alice_${unique()}`);
    const secret = `secret${unique()}`.replace(/\d/g, "x");
    await addWord(a.page, secret);
    const wordId = (await (await a.page.request.get("/api/words?language=en")).json()).items[0].id;

    const b = await newUser(browser, `bob_${unique()}`);
    await nav(b.page, "Vocabulary").click();
    await expect(b.page.getByText("No words yet")).toBeVisible();
    await expect(b.page.getByText(secret)).toHaveCount(0);

    const list = await (await b.page.request.get("/api/words?language=en")).json();
    expect(list.total).toBe(0);
    const edit = await b.page.request.patch(`/api/words/${wordId}`, { data: { meaning: "hacked" }, headers: { "X-Requested-With": "tutor" } });
    expect(edit.status()).toBe(404);                                    // 404, so existence isn't revealed either
    const del = await b.page.request.post("/api/words/delete", { data: { ids: [wordId] }, headers: { "X-Requested-With": "tutor" } });
    expect((await del.json()).deleted).toBe(0);

    await a.page.reload();                                              // and A's word is untouched
    await nav(a.page, "Vocabulary").click();
    await expect(a.page.getByRole("cell", { name: secret, exact: true })).toBeVisible();
    await a.context.close(); await b.context.close();
  });
});

test.describe("one browser, one cookie, two tabs", () => {
  test("logging in as B in tab 2 stops tab 1 from showing or acting as A", async ({ browser }) => {
    const context = await browser.newContext();
    const tab1 = await context.newPage();
    const alice = `alice_${unique()}`;
    await register(tab1, alice);
    const secret = `secret${unique()}`.replace(/\d/g, "x");
    await addWord(tab1, secret);

    const tab2 = await context.newPage();                               // same cookie jar
    await tab2.goto("/vocabulary");
    await logout(tab2);                                                 // ends alice's session everywhere
    await register(tab2, `bob_${unique()}`, "Bobby");

    // tab 1 still has alice's page open. It must drop her data and adopt whoever is logged in.
    await expect(tab1.getByText(secret)).toHaveCount(0, { timeout: 10_000 });
    await expect(tab1.getByRole("heading", { name: /Welcome, Bobby|Welcome back/ })).toBeVisible({ timeout: 10_000 });

    // and a stale alice-tab can't write into bob's account: simulate her page's request
    const res = await tab1.request.post("/api/words", {
      data: { language: "en", word: "intruder" },
      headers: { "X-Requested-With": "tutor", "X-Expected-User": "1" },
    });
    expect(res.status()).toBe(401);
    const bobsWords = await (await tab2.request.get("/api/words?language=en")).json();
    expect(bobsWords.items.map((w: { word: string }) => w.word)).not.toContain("intruder");
    await context.close();
  });

  test("logout in one tab logs the other tab out", async ({ browser }) => {
    const context = await browser.newContext();
    const tab1 = await context.newPage();
    await register(tab1, `alice_${unique()}`);
    const tab2 = await context.newPage();
    await tab2.goto("/");
    await expect(tab2.getByRole("heading", { name: /^Welcome,/ })).toBeVisible();
    await logout(tab1);
    await expect(tab2.getByRole("button", { name: "Log in", exact: true }).last()).toBeVisible({ timeout: 10_000 });
    await context.close();
  });
});

test.describe("sessions", () => {
  test("a copied cookie stops working once the owner logs out", async ({ browser }) => {
    const owner = await newUser(browser, `alice_${unique()}`);
    const cookie = (await owner.context.cookies()).find((c) => c.name === "tutor_session")!;
    expect(cookie.httpOnly).toBe(true);                                 // page scripts can't read it
    const thief = await browser.newContext();
    await thief.addCookies([cookie]);
    expect((await thief.request.get("/api/me")).status()).toBe(200);    // works while logged in

    await logout(owner.page);
    expect((await thief.request.get("/api/me")).status()).toBe(401);    // dead after logout
    await owner.context.close(); await thief.close();
  });

  test("Back after logout does not bring the previous page's data back", async ({ browser }) => {
    const { context, page } = await newUser(browser, `alice_${unique()}`);
    const secret = `secret${unique()}`.replace(/\d/g, "x");
    await addWord(page, secret);
    await logout(page);
    await expect(page.getByRole("button", { name: "Log in", exact: true }).last()).toBeVisible();
    await page.goBack();
    await page.waitForLoadState("networkidle");
    await expect(page.getByText(secret)).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Log in", exact: true }).last()).toBeVisible();
    await context.close();
  });

  test("Log out everywhere ends the other device's session too", async ({ browser }) => {
    const name = `alice_${unique()}`;
    const laptop = await newUser(browser, name);
    const phone = await browser.newContext();
    const phonePage = await phone.newPage();
    await login(phonePage, name);

    await nav(laptop.page, "Settings").click();
    await laptop.page.getByRole("button", { name: "Log out everywhere" }).click();
    await expect(laptop.page.getByRole("button", { name: "Log in", exact: true }).last()).toBeVisible();
    expect((await phone.request.get("/api/me")).status()).toBe(401);
    await laptop.context.close(); await phone.close();
  });
});

test.describe("headers and browser hardening", () => {
  test("API responses are uncacheable and the page ships a strict CSP", async ({ request }) => {
    const api = await request.get("/api/languages");
    expect(api.headers()["cache-control"]).toBe("no-store");
    expect(api.headers()["vary"]).toMatch(/cookie/i);
    const shell = await request.get("/");
    const csp = shell.headers()["content-security-policy"];
    expect(csp).toContain("script-src 'self'");
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).not.toContain("unsafe-inline");
    expect(shell.headers()["x-frame-options"]).toBe("DENY");
    expect(shell.headers()["cache-control"]).toBe("no-cache");
  });

  test("the whole app works under the CSP (no violations)", async ({ page }) => {
    const violations: string[] = [];
    page.on("console", (m) => { if (/content security policy|refused to/i.test(m.text())) violations.push(m.text()); });
    const name = `alice_${unique()}`;
    await register(page, name);
    await addWord(page, "agua");
    for (const link of ["Settings", "Home", "Vocabulary"]) await nav(page, link).click();
    await page.waitForLoadState("networkidle");
    expect(violations).toEqual([]);
  });

  test("pages do not scroll sideways on a phone", async ({ browser }) => {
    const context = await browser.newContext({ viewport: { width: 390, height: 800 } });
    const page = await context.newPage();
    await page.goto("/login");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await register(page, `alice_${unique()}`);
    await nav(page, "Vocabulary").click();
    await page.getByRole("heading", { name: /Vocabulary/ }).waitFor();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await context.close();
  });
});
