import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ALICE, err, LANGS, mockApi, renderApp } from "../test/helpers";

afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); });
const META = { policy_version: "2026-10-06", privacy_contact: null };

describe("privacy policy page", () => {
  it("is readable without logging in", async () => {
    mockApi({ "GET /me": err(401, "unauthorized", "x"), "GET /languages": LANGS, "GET /meta": META });
    renderApp("/privacy");
    expect(await screen.findByRole("heading", { level: 1, name: "Privacy Policy" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Back to sign in/ })).toHaveAttribute("href", "/login");
  });

  it("says name and email are the only personal information, and lists everything else honestly", async () => {
    mockApi({ "GET /me": err(401, "unauthorized", "x"), "GET /languages": LANGS, "GET /meta": META });
    renderApp("/privacy");
    await screen.findByRole("heading", { level: 1, name: "Privacy Policy" });
    expect(screen.getByText(/only personal information we ask for is your/)).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Information the app stores" });
    for (const row of ["Your name", "Your email address", "Your password", "Words, meanings and stories you add", "Sign-in records", "Proof you accepted this policy"])
      expect(within(table).getByText(row)).toBeInTheDocument();
    expect(within(table).getByText(/Stored only as a scrambled one-way hash/)).toBeInTheDocument();
  });

  it("covers the promises the app keeps: cookie, AI sharing, deletion, export, rights", async () => {
    mockApi({ "GET /me": err(401, "unauthorized", "x"), "GET /languages": LANGS, "GET /meta": META });
    renderApp("/privacy");
    await screen.findByRole("heading", { level: 1, name: "Privacy Policy" });
    const text = document.body.textContent ?? "";
    for (const claim of [
      "one cookie", "Groq", "not sent", "Delete account", "Download my data", "do not sell", "does not send you any email",
      "under 16", "data protection authority",
    ]) expect(text, `policy should mention "${claim}"`).toContain(claim);
    for (const h of ["Who this applies to", "What we collect", "How we use it", "Cookies and browser storage", "Who we share it with",
      "How long we keep it", "Your choices and rights", "How we protect it", "Children", "Changes to this policy", "Contact"])
      expect(screen.getByRole("heading", { level: 2, name: new RegExp(h) })).toBeInTheDocument();
  });

  it("shows the policy version and the operator's contact address when configured", async () => {
    mockApi({ "GET /me": err(401, "unauthorized", "x"), "GET /languages": LANGS, "GET /meta": { policy_version: "2026-10-06", privacy_contact: "privacy@school.example" } });
    renderApp("/privacy");
    expect(await screen.findByText(/Version 2026-10-06/)).toBeInTheDocument();
    const links = await screen.findAllByRole("link", { name: "privacy@school.example" });
    expect(links[0]).toHaveAttribute("href", "mailto:privacy@school.example");
  });

  it("without a configured contact it points at whoever runs the installation", async () => {
    mockApi({ "GET /me": err(401, "unauthorized", "x"), "GET /languages": LANGS, "GET /meta": META });
    renderApp("/privacy");
    expect((await screen.findAllByText(/contact the person who (runs|gave you access)/)).length).toBeGreaterThan(0);
  });

  it("logged-in users get a link back into the app", async () => {
    mockApi({ "GET /me": ALICE, "GET /languages": LANGS, "GET /meta": META });
    renderApp("/privacy");
    expect(await screen.findByRole("link", { name: /Back to the app/ })).toHaveAttribute("href", "/settings");
  });
});
