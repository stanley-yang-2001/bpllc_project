import { expect, test } from "@playwright/test";
import { addWord, emailOf, login, loginButton, nav, PASSWORD, register, unique } from "./helpers";

test.describe("sign-up collects name and email, and consent", () => {
  test("the form asks for exactly name, email and password, and blocks without the checkbox", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("tab", { name: "Create account" }).click();
    await expect(page.getByLabel("Your name")).toBeVisible();
    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByLabel("Username")).toHaveCount(0);
    await page.getByLabel("Your name").fill("Pat Doe");
    await page.getByLabel("Email").fill(emailOf(`pat_${unique()}`));
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page.getByText("You need to accept the privacy policy to create an account")).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);                                       // not signed up
  });

  test("a bad email is refused before anything is sent", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("tab", { name: "Create account" }).click();
    await page.getByLabel("Your name").fill("Pat");
    await page.getByLabel("Email").fill("pat-at-example");
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await page.getByRole("checkbox", { name: /Privacy Policy/ }).check();
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page.getByText("Enter a valid email address")).toBeVisible();
  });

  test("the policy opens in a new tab and the half-filled form is kept", async ({ page, context }) => {
    await page.goto("/login");
    await page.getByRole("tab", { name: "Create account" }).click();
    await page.getByLabel("Your name").fill("Pat Doe");
    const [policy] = await Promise.all([context.waitForEvent("page"), page.getByRole("link", { name: "Privacy Policy" }).first().click()]);
    await expect(policy.getByRole("heading", { level: 1, name: "Privacy Policy" })).toBeVisible();
    await expect(policy.getByText(/only personal information we ask for is your/)).toBeVisible();
    await expect(page.getByLabel("Your name")).toHaveValue("Pat Doe");
  });

  test("signing up with a taken email says so, and email is case-insensitive", async ({ page, browser }) => {
    const local = `pat_${unique()}`;
    await register(page, local);
    const other = await (await browser.newContext()).newPage();
    await other.goto("/login");
    await other.getByRole("tab", { name: "Create account" }).click();
    await other.getByLabel("Your name").fill("Someone");
    await other.getByLabel("Email").fill(emailOf(local).toUpperCase());
    await other.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await other.getByRole("checkbox", { name: /Privacy Policy/ }).check();
    await other.getByRole("button", { name: "Create account" }).click();
    await expect(other.getByRole("alert")).toContainText("already exists");
  });

  test("the privacy page is public and the app has a footer link to it", async ({ page }) => {
    await page.goto("/privacy");
    await expect(page.getByRole("heading", { level: 1, name: "Privacy Policy" })).toBeVisible();
    await expect(page.getByRole("table", { name: "Information the app stores" })).toBeVisible();
    await register(page, `pat_${unique()}`);
    await page.getByRole("contentinfo").getByRole("link", { name: "Privacy Policy" }).click();
    await expect(page.getByRole("link", { name: /Back to the app/ })).toBeVisible();
  });
});

test.describe("settings", () => {
  test("changing name, email and password works end to end", async ({ page, browser }) => {
    const local = `pat_${unique()}`;
    await register(page, local, "Pat");
    await nav(page, "Settings").click();

    await page.getByLabel("Your name").fill("Pat Renamed");
    await page.getByRole("button", { name: "Save profile" }).click();
    await expect(page.getByText("Profile saved")).toBeVisible();

    const newLocal = `moved_${unique()}`;
    await page.getByLabel("New email").fill(emailOf(newLocal));
    await page.locator("#e-pass").fill("wrong-password");
    await page.getByRole("button", { name: "Change email" }).click();
    await expect(page.getByRole("alert")).toContainText("That password is not correct.");
    await page.locator("#e-pass").fill(PASSWORD);
    await page.getByRole("button", { name: "Change email" }).click();
    await expect(page.getByText("Email address changed")).toBeVisible();

    await page.locator("#pw-cur").fill(PASSWORD);
    await page.getByLabel("New password", { exact: true }).fill("a-brand-new-password");
    await page.getByLabel("New password again").fill("a-brand-new-password");
    await page.getByRole("button", { name: "Change password" }).click();
    await expect(page.getByText(/other devices were logged out/)).toBeVisible();

    const fresh = await (await browser.newContext()).newPage();
    await login(fresh, local);                                                      // old email: refused
    await expect(fresh.getByRole("alert")).toContainText("Wrong email or password.");
    await login(fresh, newLocal, PASSWORD);                                          // old password: refused
    await expect(fresh.getByRole("alert")).toContainText("Wrong email or password.");
    await login(fresh, newLocal, "a-brand-new-password");
    await expect(fresh.getByRole("heading", { name: "Welcome, Pat Renamed" })).toBeVisible();
  });

  test("Download my data gives a JSON file with only my information", async ({ page, browser }) => {
    const bob = await (await browser.newContext()).newPage();
    await register(bob, `bob_${unique()}`);
    await addWord(bob, "bobsecret");

    const local = `pat_${unique()}`;
    await register(page, local, "Pat");
    await addWord(page, "agua", "water");
    await nav(page, "Settings").click();
    const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Download my data" }).click()]);
    expect(download.suggestedFilename()).toMatch(/^language-tutor-my-data-\d{4}-\d{2}-\d{2}\.json$/);
    const text = await (await import("node:fs/promises")).readFile((await download.path())!, "utf8");
    const data = JSON.parse(text);
    expect(data.profile.email).toBe(emailOf(local));
    expect(data.profile.display_name).toBe("Pat");
    expect(data.words).toEqual([expect.objectContaining({ word: "agua", meaning: "water" })]);
    expect(text).not.toContain("bobsecret");
    expect(text.toLowerCase()).not.toContain("password");
  });

  test("deleting the account removes everything, logs out other tabs, and frees the email", async ({ browser }) => {
    const context = await browser.newContext();
    const tab1 = await context.newPage();
    const local = `pat_${unique()}`;
    await register(tab1, local, "Pat");
    await addWord(tab1, "doomed");
    const tab2 = await context.newPage();
    await tab2.goto("/vocabulary");
    await expect(tab2.getByRole("cell", { name: "doomed", exact: true })).toBeVisible();

    await nav(tab1, "Settings").click();
    await tab1.getByRole("button", { name: "Delete account" }).click();
    const dialog = tab1.getByRole("dialog");
    await expect(dialog.getByLabel("Enter your password to confirm")).toBeFocused();   // ready to type
    await expect(dialog.getByRole("button", { name: "Delete my account" })).toBeDisabled();
    await dialog.getByLabel("Enter your password to confirm").fill("wrong-password");
    await dialog.getByRole("button", { name: "Delete my account" }).click();
    await expect(dialog.getByRole("alert")).toContainText("That password is not correct.");
    await expect(tab1.getByRole("heading", { name: "Settings" })).toBeVisible();      // still here

    await dialog.getByLabel("Enter your password to confirm").fill(PASSWORD);
    await dialog.getByRole("button", { name: "Delete my account" }).click();
    await expect(loginButton(tab1)).toBeVisible();
    await expect(loginButton(tab2)).toBeVisible({ timeout: 10_000 });                  // the other tab noticed
    await expect(tab2.getByText("doomed")).toHaveCount(0);

    await login(tab1, local);
    await expect(tab1.getByRole("alert")).toContainText("Wrong email or password.");   // the account is gone
    await register(tab1, local, "Pat again");                                          // email is free; nothing carried over
    await nav(tab1, "Vocabulary").click();
    await expect(tab1.getByText("No words yet")).toBeVisible();
  });
});

test.describe("dialogs, keyboard", () => {
  test("deleting words: Cancel is focused first, Escape cancels, focus goes back, Delete deletes", async ({ page }) => {
    await register(page, `pat_${unique()}`);
    await addWord(page, "uno");
    await addWord(page, "dos");
    await page.getByLabel("Select uno").check();
    const opener = page.getByRole("button", { name: /Delete selected/ });
    await opener.click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByRole("button", { name: "Cancel" })).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(page.getByRole("cell", { name: "uno", exact: true })).toBeVisible();   // nothing deleted
    await expect(opener).toBeFocused();                                                  // focus handed back

    await opener.click();
    await page.getByRole("dialog").getByRole("button", { name: "Delete word" }).click();
    await expect(page.getByRole("cell", { name: "uno", exact: true })).toHaveCount(0);
    await expect(page.getByText("Deleted 1 word")).toBeVisible();
    await expect(page.getByRole("cell", { name: "dos", exact: true })).toBeVisible();
  });

  test("keyboard focus never lands on the page behind an open dialog", async ({ page }) => {
    await register(page, `pat_${unique()}`);
    await nav(page, "Settings").click();
    await page.getByRole("button", { name: "Delete account" }).click();
    for (let i = 0; i < 10; i++) {
      await page.keyboard.press("Tab");
      // Tab may leave the page for the browser's own toolbar (activeElement is then <body>); it must not reach the
      // page content behind the dialog, which the browser makes inert.
      const ok = await page.evaluate(() => {
        const a = document.activeElement;
        return !a || a === document.body || !!a.closest("dialog");
      });
      expect(ok, `after Tab #${i + 1}`).toBe(true);
    }
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Delete account" })).toBeFocused();     // focus handed back to the opener
  });
});

test.describe("dark mode", () => {
  test("follows the OS with no light flash, can be overridden, and the choice survives a reload", async ({ browser }) => {
    const context = await browser.newContext({ colorScheme: "dark" });
    const page = await context.newPage();
    await page.goto("/login");
    expect(await page.evaluate(() => document.documentElement.classList.contains("dark"))).toBe(true);
    const bg = () => page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    expect(await bg()).toBe("rgb(2, 6, 23)");                                          // the dark page colour, not white

    await page.getByRole("button", { name: "Switch to light mode" }).click();
    expect(await page.evaluate(() => document.documentElement.classList.contains("dark"))).toBe(false);
    await page.reload();
    expect(await page.evaluate(() => document.documentElement.classList.contains("dark"))).toBe(false);   // explicit choice beats the OS

    await register(page, `pat_${unique()}`);
    await nav(page, "Settings").click();
    await page.getByRole("radio", { name: "System" }).check({ force: true });
    expect(await page.evaluate(() => document.documentElement.classList.contains("dark"))).toBe(true);
    await page.emulateMedia({ colorScheme: "light" });                                  // OS switches while on System
    await expect.poll(() => page.evaluate(() => document.documentElement.classList.contains("dark"))).toBe(false);
    await context.close();
  });

  test("the page is already dark before any app code runs (no white flash)", async ({ browser }) => {
    const context = await browser.newContext({ colorScheme: "dark" });
    const page = await context.newPage();
    await page.route("**/assets/*.js", (route) => route.abort());          // the React app never starts
    await page.goto("/login");
    expect(await page.evaluate(() => document.getElementById("root")!.childElementCount)).toBe(0);   // proof it didn't run
    expect(await page.evaluate(() => document.documentElement.classList.contains("dark"))).toBe(true);
    expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).toBe("rgb(2, 6, 23)");
    await context.close();
  });

  test("a saved light choice also applies before the app starts, even if the OS is dark", async ({ browser }) => {
    const context = await browser.newContext({ colorScheme: "dark" });
    await context.addInitScript(() => localStorage.setItem("tutor:theme", "light"));
    const page = await context.newPage();
    await page.route("**/assets/*.js", (route) => route.abort());
    await page.goto("/login");
    expect(await page.evaluate(() => document.documentElement.classList.contains("dark"))).toBe(false);
    await context.close();
  });

  test("dark mode survives logout (it is a device setting, not account data)", async ({ browser }) => {
    const context = await browser.newContext({ colorScheme: "light" });
    const page = await context.newPage();
    await register(page, `pat_${unique()}`);
    await page.getByRole("button", { name: "Switch to dark mode" }).click();
    await page.getByRole("button", { name: "Log out", exact: true }).click();
    await expect(loginButton(page)).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.classList.contains("dark"))).toBe(true);
    await context.close();
  });
});
