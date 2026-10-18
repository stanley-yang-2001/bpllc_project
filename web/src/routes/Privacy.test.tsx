import { readFileSync } from "node:fs";
import { join } from "node:path";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ALICE, err, LANGS, mockApi, renderApp } from "../test/helpers";

afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); });
const EN = JSON.parse(readFileSync(join(process.cwd(), "../api/app/policy/en.json"), "utf8"));   // the real English copy
const META = { policy_version: EN.version, privacy_contact: null, policy_languages: ["en"] };
const policyApi = (copies: Record<string, any> = { en: EN }) => ({ path }: { path: string }) => {
  const lang = new URL(path, "http://x").searchParams.get("lang");
  const doc = lang && copies[lang] ? copies[lang] : copies.en;
  return { json: { language: doc.language, version: doc.version, fallback: !!lang && lang !== doc.language, doc } };
};
const base = { "GET /me": err(401, "unauthorized", "x"), "GET /languages": LANGS, "GET /meta": META, "GET /policy": policyApi() };

describe("privacy policy page", () => {
  it("is readable without logging in", async () => {
    mockApi(base);
    renderApp("/privacy");
    expect(await screen.findByRole("heading", { level: 1, name: "Privacy Policy" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Back to sign in/ })).toHaveAttribute("href", "/login");
  });

  it("says name and email are the only personal information, and lists everything else honestly", async () => {
    mockApi(base);
    renderApp("/privacy");
    await screen.findByRole("heading", { level: 1, name: "Privacy Policy" });
    expect(screen.getByText(/only personal information we ask for is your/)).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Information the app stores" });
    for (const row of ["Your name", "Your email address", "Your password", "Words, meanings and stories you add", "Your display preferences", "Sign-in records", "Proof you accepted this policy"])
      expect(within(table).getByText(row)).toBeInTheDocument();
    expect(within(table).getByText(/Stored only as a scrambled one-way hash/)).toBeInTheDocument();
  });

  it("covers the promises the app keeps: cookie, AI sharing, deletion, export, rights", async () => {
    mockApi(base);
    renderApp("/privacy");
    await screen.findByRole("heading", { level: 1, name: "Privacy Policy" });
    const text = document.body.textContent ?? "";
    for (const claim of [
      "one cookie", "Groq", "not sent", "Delete account", "Download my data", "do not sell", "does not send you any email",
      "under 16", "data protection authority", "Your chat with the tutor", "chat history", "random salt", "not the messages", "Save to library", "saved stories", "display preferences", "temporary copy", "removed when you sign out", "A story you do not save is not kept",
    ]) expect(text, `policy should mention "${claim}"`).toContain(claim);
    for (const h of ["Who this applies to", "What we collect", "How we use it", "Cookies and browser storage", "Who we share it with",
      "How long we keep it", "Your choices and rights", "How we protect it", "Children", "Changes to this policy", "Copies in other languages", "Contact"])
      expect(screen.getByRole("heading", { level: 2, name: new RegExp(h) })).toBeInTheDocument();
  });

  it("shows the policy version and the operator's contact address when configured", async () => {
    mockApi({ "GET /me": err(401, "unauthorized", "x"), "GET /languages": LANGS, "GET /meta": { ...META, privacy_contact: "privacy@school.example" }, "GET /policy": policyApi() });
    renderApp("/privacy");
    expect(await screen.findByText(new RegExp(`Version ${EN.version}`))).toBeInTheDocument();
    const links = await screen.findAllByRole("link", { name: "privacy@school.example" });
    expect(links[0]).toHaveAttribute("href", "mailto:privacy@school.example");
  });

  it("without a configured contact it points at whoever runs the installation", async () => {
    mockApi(base);
    renderApp("/privacy");
    expect((await screen.findAllByText(/contact the person who (runs|gave you access)/)).length).toBeGreaterThan(0);
  });

  it("logged-in users get a link back into the app", async () => {
    mockApi({ ...base, "GET /me": ALICE });
    renderApp("/privacy");
    expect(await screen.findByRole("link", { name: /Back to the app/ })).toHaveAttribute("href", "/settings");
  });

  it("shows a copy's text as text: markup inside a string is never turned into elements", async () => {
    const evil = JSON.parse(JSON.stringify(EN));
    evil.sections[0].blocks[0].text = "<img src=x onerror=alert(1)> and <b>not bold</b> and **bold** {contact}";
    evil.sections[0].blocks[0].text_without_contact = evil.sections[0].blocks[0].text;
    mockApi({ ...base, "GET /policy": policyApi({ en: evil }) });
    const { ui } = renderApp("/privacy");
    expect(await screen.findByText(/<img src=x onerror=alert\(1\)>/)).toBeInTheDocument();
    expect(ui.container.querySelector("img")).toBeNull();
    expect(ui.container.querySelector("b")).toBeNull();
    expect(screen.getByText("bold", { selector: "strong" })).toBeInTheDocument();
  });

  it("states which copy governs", async () => {
    mockApi(base);
    renderApp("/privacy");
    expect(await screen.findByText(EN.governing)).toBeInTheDocument();
    expect(screen.getByText(/If copies ever disagree, the English copy governs/)).toBeInTheDocument();
  });
});

describe("privacy policy page, copies in other languages", () => {
  const ES = { ...JSON.parse(JSON.stringify(EN)), language: "es", title: "Política de privacidad", governing: "Si hay desacuerdo, prevalece la copia en inglés." };
  const withEs = { ...base, "GET /meta": { ...META, policy_languages: ["en", "es"] }, "GET /policy": policyApi({ en: EN, es: ES }) };

  it("has no picker when English is the only approved copy", async () => {
    mockApi(base);
    renderApp("/privacy");
    await screen.findByRole("heading", { level: 1, name: "Privacy Policy" });
    expect(screen.queryByLabelText("Language of this policy")).not.toBeInTheDocument();
  });

  it("lists only the approved languages, each in its own name, and a signed-out visitor can switch", async () => {
    mockApi(withEs);
    renderApp("/privacy");
    const picker = await screen.findByLabelText("Language of this policy");
    expect([...(picker as HTMLSelectElement).options].map((o) => o.textContent)).toEqual(["English", "Español"]);
    await userEvent.selectOptions(picker, "es");
    const h1 = await screen.findByRole("heading", { level: 1, name: "Política de privacidad" });
    expect(h1.closest("[lang]")).toHaveAttribute("lang", "es");
  });

  it("follows the interface language when an approved copy exists", async () => {
    mockApi({ ...withEs, "GET /me": { ...ALICE, languages: ["en", "es"], preferences: { active_language: "es", ui_follows_study_language: true, theme: "system", custom_colors: null } } });
    renderApp("/privacy");
    expect(await screen.findByRole("heading", { level: 1, name: "Política de privacidad" })).toBeInTheDocument();
    expect(screen.queryByText(/Showing the English copy/)).not.toBeInTheDocument();
  });

  it("falls back to English with a notice in the interface language when there is no approved copy", async () => {
    mockApi({ ...base, "GET /me": { ...ALICE, languages: ["en", "ja"], preferences: { active_language: "ja", ui_follows_study_language: true, theme: "system", custom_colors: null } } });
    renderApp("/privacy");
    expect(await screen.findByRole("heading", { level: 1, name: "Privacy Policy" })).toBeInTheDocument();
    expect(await screen.findByText("このポリシーはまだあなたの言語では利用できません。英語版を表示しています。")).toBeInTheDocument();
  });
});
