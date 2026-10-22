import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { addWord, nav, register, unique } from "./helpers";

/** Themes, the colour wheel and the site language, in a real browser with the production Content-Security-Policy. */
async function scan(page: Page, label: string) {
  // A button that is still loading (spinner) is mid-transition and is disabled for a moment; wait for it, or the scan is flaky.
  await expect(page.locator(".animate-spin")).toHaveCount(0);
  await page.waitForTimeout(300);
  const { violations } = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  const summary = violations.map((v) => `${v.id}: ${v.help}\n   ${v.nodes.slice(0, 3).map((n) => n.target.join(" ") + " :: " + (n.any[0]?.message ?? n.failureSummary?.split("\n")[1] ?? "")).join("\n   ")}`);
  expect(summary, `${label}\n${summary.join("\n")}`).toEqual([]);
}
const cssVar = (page: Page, name: string) => page.evaluate((n) => document.documentElement.style.getPropertyValue(n), name);
const watchCsp = (page: Page) => {
  const bad: string[] = [];
  page.on("console", (m) => { if (/Content Security Policy|Refused to/i.test(m.text())) bad.push(m.text()); });
  page.on("pageerror", (e) => bad.push(String(e)));
  return bad;
};
const openAppearance = async (page: Page) => { await nav(page, "Settings").click(); await expect(page.getByRole("radiogroup", { name: "Theme" })).toBeVisible(); };

test.describe("themes and the colour wheel", () => {
  test("a real click on the wheel recolours the page, with no CSP violation, and survives a reload with no flash", async ({ browser }) => {
    const ctx = await browser.newContext({ colorScheme: "light" });
    const page = await ctx.newPage();
    const bad = watchCsp(page);
    await register(page, `pat_${unique()}`);
    await openAppearance(page);
    await page.getByRole("radio", { name: "Custom" }).check({ force: true });
    await page.getByRole("radio", { name: "Page background" }).check({ force: true });
    const before = await cssVar(page, "--color-slate-50");
    const wheel = page.getByRole("slider", { name: "Color wheel: Page background" });
    const box = (await wheel.boundingBox())!;
    await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.08);     // top edge: red, full strength
    await expect.poll(() => cssVar(page, "--color-slate-50")).not.toBe(before);
    const picked = await cssVar(page, "--color-slate-50");
    expect(picked).toMatch(/^#[0-9a-f]{6}$/);
    expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).not.toBe("rgb(255, 255, 255)");
    await page.waitForTimeout(1500);                                              // the save is sent after a short pause

    // reload with the app's own script blocked: the init script alone must already have themed the page
    await page.route("**/assets/*.js", (route) => route.abort());
    await page.reload();
    expect(await cssVar(page, "--color-slate-50")).toBe(picked);
    expect(bad).toEqual([]);
    await ctx.close();
  });

  test("a preset is saved to the account and shows on a second browser", async ({ browser }) => {
    const first = await browser.newContext({ colorScheme: "light" });
    const page = await first.newPage();
    const local = `pat_${unique()}`;
    await register(page, local);
    await openAppearance(page);
    await page.getByRole("radio", { name: "Midnight" }).check({ force: true });
    await expect.poll(() => page.evaluate(() => document.documentElement.classList.contains("dark"))).toBe(true);
    await page.waitForTimeout(1500);
    const second = await browser.newContext({ colorScheme: "light" });
    const other = await second.newPage();
    await other.goto("/login");
    await other.getByLabel("Email").fill(`${local}@example.com`);
    await other.getByLabel("Password", { exact: true }).fill("password123");
    await other.getByRole("button", { name: "Log in", exact: true }).last().click();
    await expect.poll(() => cssVar(other, "--color-slate-50")).toBe("#070b1a");
    await first.close();
    await second.close();
  });

  for (const preset of ["Ocean", "Forest", "Sunset", "Rose", "Midnight", "Graphite", "High contrast"]) {
    test(`accessibility scan of the main screens under ${preset}`, async ({ page }) => {
      await register(page, `pat_${unique()}`);
      await addWord(page, "hello", "a greeting");
      await openAppearance(page);
      await page.getByRole("radio", { name: preset, exact: true }).check({ force: true });
      await scan(page, `settings (${preset})`);
      await nav(page, "Home").click();
      await scan(page, `home (${preset})`);
      await nav(page, "Vocabulary").click();
      await scan(page, `vocabulary (${preset})`);
      await nav(page, "Chat").click();
      await scan(page, `chat (${preset})`);
    });
  }

  for (const [name, c] of Object.entries({
    veryLight: { page: "#ffffff", cards: "#fafafa", text: "#222222", borders: "#e5e5e5", accent: "#ffd400" },
    veryDark: { page: "#000000", cards: "#0a0a0a", text: "#ffffff", borders: "#2a2a2a", accent: "#00ffaa" },
    saturated: { page: "#ffe600", cards: "#fff3a0", text: "#000000", borders: "#b39b00", accent: "#ff00aa" },
  })) {
    test(`accessibility scan of a custom palette: ${name}`, async ({ page }) => {
      await register(page, `pat_${unique()}`);
      await openAppearance(page);
      await page.getByRole("radio", { name: "Custom" }).check({ force: true });
      for (const [part, label] of [["page", "Page background"], ["cards", "Cards and panels"], ["text", "Text"], ["borders", "Borders"], ["accent", "Buttons, links and menu"]] as const) {
        await page.getByRole("radio", { name: label }).check({ force: true });
        const hex = page.getByLabel("Hex color");
        await hex.fill((c as Record<string, string>)[part]);
      }
      await scan(page, `settings with a custom palette (${name})`);
      await nav(page, "Home").click();
      await scan(page, `home with a custom palette (${name})`);
    });
  }
});

test.describe("the site in the study language", () => {
  async function studySpanish(page: Page) {
    await register(page, `pat_${unique()}`);
    await nav(page, "Vocabulary").click();
    await page.getByLabel("Language to start").selectOption("es");
    await page.getByRole("button", { name: "Add", exact: true }).click();
    await expect(page.getByLabel("Active language")).toHaveValue("es");
  }

  test("the checkbox switches menus and page text, sets <html lang>, and survives a reload", async ({ page }) => {
    await studySpanish(page);
    await nav(page, "Settings").click();
    await page.getByRole("checkbox", { name: "Use my study language for the site" }).check();
    await expect(page.getByRole("navigation", { name: "Principal" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Inicio" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.lang)).toBe("es");
    await page.waitForTimeout(1500);
    await page.reload();
    await expect(page.getByRole("link", { name: "Inicio" })).toBeVisible();
    await scan(page, "settings in Spanish");
    await page.getByRole("link", { name: "Inicio" }).click();
    await scan(page, "home in Spanish");
  });

  test("the policy page follows the interface language: no approved copy yet, so English with a notice in Spanish", async ({ page }) => {
    await studySpanish(page);
    await nav(page, "Settings").click();
    await page.getByRole("checkbox", { name: "Use my study language for the site" }).check();
    await page.waitForTimeout(1500);
    await page.goto("/privacy");
    await expect(page.getByRole("heading", { level: 1, name: "Privacy Policy" })).toBeVisible();
    await expect(page.getByText("Esta política aún no está disponible en tu idioma. Se muestra la copia en inglés.")).toBeVisible();
    await scan(page, "privacy with a fallback notice");
  });

  test("logging out returns the sign-in page to English", async ({ page }) => {
    await studySpanish(page);
    await nav(page, "Settings").click();
    await page.getByRole("checkbox", { name: "Use my study language for the site" }).check();
    await page.waitForTimeout(1500);
    await page.getByRole("button", { name: "Cerrar sesión", exact: true }).click();
    await expect(page.getByRole("tab", { name: "Create account" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.lang)).toBe("en");
  });
});

test("accessibility scan of Home and Settings in every site language (including the CJK font stacks)", async ({ page }) => {
  test.setTimeout(180_000);
  await register(page, `pat_${unique()}`);
  const others = ["es", "fr", "de", "it", "pt", "ja", "zh", "ko"];
  for (const code of others) {
    await nav(page, "Vocabulary").click();
    await page.getByLabel("Language to start").selectOption(code);
    await page.getByRole("button", { name: "Add", exact: true }).click();
    await expect(page.getByLabel("Active language")).toHaveValue(code);
  }
  await nav(page, "Settings").click();
  await page.getByRole("checkbox", { name: "Use my study language for the site" }).check();
  for (const code of ["es", "fr", "de", "it", "pt", "ja", "zh", "ko"]) {
    await page.getByLabel(/./, { exact: false }).first();                       // keep the page settled
    await page.locator("header select").first().selectOption(code);
    await expect.poll(() => page.evaluate(() => document.documentElement.lang)).toBe(code === "zh" ? "zh-Hans" : code);
    await scan(page, `settings (${code})`);
    await page.locator("header a[href='/']").first().click();
    await scan(page, `home (${code})`);
    await page.locator("nav a[href='/settings']").click();
  }
});
