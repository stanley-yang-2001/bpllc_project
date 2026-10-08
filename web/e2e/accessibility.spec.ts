import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { addWord, nav, register, unique } from "./helpers";

/** Automated checks (axe-core, WCAG 2 A/AA rules including colour contrast) on every screen, in both themes.
 * Automated tools find about a third of accessibility problems; this is a floor, not a certificate. */
async function scan(page: Page, label: string) {
  const { violations } = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  const summary = violations.map((v) => `${v.id}: ${v.help}\n   ${v.nodes.slice(0, 3).map((n) => n.target.join(" ") + " :: " + (n.any[0]?.message ?? n.failureSummary?.split("\n")[1] ?? "")).join("\n   ")}`);
  expect(summary, `${label}\n${summary.join("\n")}`).toEqual([]);
}

for (const scheme of ["light", "dark"] as const) {
  test.describe(`${scheme} theme`, () => {
    test.use({ colorScheme: scheme });

    test("sign-in, sign-up and privacy pages", async ({ page }) => {
      await page.goto("/login");
      await scan(page, `login (${scheme})`);
      await page.getByRole("tab", { name: "Create account" }).click();
      await page.getByRole("button", { name: "Create account" }).click();         // show every validation error
      await expect(page.getByText("Enter your name")).toBeVisible();
      await scan(page, `sign-up with errors (${scheme})`);
      await page.goto("/privacy");
      await scan(page, `privacy (${scheme})`);
    });

    test("every signed-in screen, dialogs included", async ({ page }) => {
      await register(page, `pat_${unique()}`, "Pat Doe");
      await scan(page, `home, empty (${scheme})`);
      await addWord(page, "uno", "one");
      await addWord(page, "dos");
      await page.getByLabel("Select uno").check();
      await scan(page, `vocabulary with selection bar (${scheme})`);
      await page.getByRole("button", { name: /Delete selected/ }).click();
      await scan(page, `confirm dialog (${scheme})`);
      await page.keyboard.press("Escape");
      await page.getByLabel("Word", { exact: true }).fill("uno");
      await page.getByRole("button", { name: "Add word" }).click();
      await expect(page.getByRole("alert")).toBeVisible();
      await scan(page, `vocabulary with an error (${scheme})`);
      for (const name of ["Chat", "Studio", "Library", "Practice"]) { await nav(page, name).click(); await scan(page, `${name} placeholder (${scheme})`); }
      await nav(page, "Settings").click();
      await expect(page.getByText("Postgres")).toBeVisible();
      await scan(page, `settings (${scheme})`);
      await page.getByRole("button", { name: "Delete account" }).click();
      await scan(page, `delete-account dialog (${scheme})`);
    });
  });
}
