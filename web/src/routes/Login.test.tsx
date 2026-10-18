import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ALICE, err, LANGS, mockApi, renderApp } from "../test/helpers";

afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });

const loggedOut = { "GET /me": err(401, "unauthorized", "Please log in."), "GET /languages": LANGS };

describe("login page", () => {
  it("redirects anonymous visitors to /login", async () => {
    mockApi(loggedOut);
    renderApp("/vocabulary");
    expect(await screen.findByRole("button", { name: "Log in" })).toBeInTheDocument();
  });

  it("validates before calling the server", async () => {
    const { calls } = mockApi(loggedOut);
    renderApp("/login");
    await userEvent.click(await screen.findByRole("button", { name: "Log in" }));
    expect(await screen.findByText("Enter your email")).toBeInTheDocument();
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  });

  it("shows the server's message for a wrong password", async () => {
    mockApi({ ...loggedOut, "POST /auth/login": err(401, "login_failed", "Wrong email or password.") });
    renderApp("/login");
    await userEvent.type(await screen.findByLabelText("Email"), "alice@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "nope");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Wrong email or password.");
  });

  it("logs in and lands on Home", async () => {
    mockApi({ ...loggedOut, "POST /auth/login": ALICE, "GET /words": { items: [], total: 0, limit: 1, offset: 0 } });
    renderApp("/login");
    await userEvent.type(await screen.findByLabelText("Email"), "alice@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "password123");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByText("Welcome, Alice")).toBeInTheDocument();
  });

  it("registration asks for name and email, enforces the rules, and needs the privacy checkbox", async () => {
    const { calls } = mockApi({ ...loggedOut, "POST /auth/register": { ...ALICE, languages: ["es"] }, "GET /words": { items: [], total: 0, limit: 1, offset: 0 } });
    renderApp("/login");
    await userEvent.click(await screen.findByRole("tab", { name: "Create account" }));
    expect(screen.getByLabelText("Your name")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.queryByLabelText("Username")).not.toBeInTheDocument();       // no separate username any more

    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Enter your name")).toBeInTheDocument();
    expect(screen.getByText("At least 8 characters")).toBeInTheDocument();
    expect(screen.getByText("You need to accept the privacy policy to create an account")).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Your name"), "Alice A");
    await userEvent.type(screen.getByLabelText("Email"), "not-an-email");
    await userEvent.type(screen.getByLabelText("Password"), "password123");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Enter a valid email address")).toBeInTheDocument();
    expect(calls.some((c) => c.path === "/auth/register")).toBe(false);          // nothing sent yet

    await userEvent.clear(screen.getByLabelText("Email"));
    await userEvent.type(screen.getByLabelText("Email"), " Alice@Example.com ");
    await userEvent.selectOptions(screen.getByLabelText("Language I'm learning"), "es");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("You need to accept the privacy policy to create an account")).toBeInTheDocument();
    expect(calls.some((c) => c.path === "/auth/register")).toBe(false);          // still blocked without consent

    await userEvent.click(screen.getByRole("checkbox", { name: /Privacy Policy/ }));
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() => expect(calls.find((c) => c.path === "/auth/register")).toBeTruthy());
    expect(calls.find((c) => c.path === "/auth/register")!.body).toEqual({
      display_name: "Alice A", email: "alice@example.com", password: "password123", language: "es", accept_privacy: true,
    });
  });

  it("the sign-up form links to the privacy policy and says what is kept", async () => {
    mockApi(loggedOut);
    renderApp("/login");
    await userEvent.click(await screen.findByRole("tab", { name: "Create account" }));
    const links = screen.getAllByRole("link", { name: "Privacy Policy" });      // the consent link and the page footer
    expect(links).toHaveLength(2);
    const link = links.find((a) => a.getAttribute("target") === "_blank")!;     // opens in a new tab so the form isn't lost
    expect(link).toHaveAttribute("href", "/privacy");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
    expect(screen.getByText(/We keep your name and email to run your account/)).toBeInTheDocument();
  });

  it("logout clears cached data and session storage", async () => {
    mockApi({ "GET /me": ALICE, "GET /languages": LANGS, "GET /words": { items: [], total: 0, limit: 1, offset: 0 }, "POST /auth/logout": () => ({ status: 204 }) });
    sessionStorage.setItem("chat", "private");
    const { client } = renderApp("/");
    await screen.findByText("Welcome, Alice");
    expect(client.getQueryCache().findAll({ queryKey: ["words"] }).length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole("button", { name: "Log out" }));
    expect(await screen.findByRole("button", { name: "Log in" })).toBeInTheDocument();
    expect(sessionStorage.getItem("chat")).toBeNull();
    expect(client.getQueryCache().findAll({ queryKey: ["words"] })).toHaveLength(0);
  });

  it("saves the active language on the account, not on the device", async () => {
    const { calls } = mockApi({
      "GET /me": { ...ALICE, languages: ["en", "es"], preferences: null }, "GET /languages": LANGS, "GET /words": { items: [], total: 0, limit: 1, offset: 0 },
      "PATCH /me/preferences": ({ body }: any) => ({ json: { active_language: null, ui_follows_study_language: false, theme: "system", custom_colors: null, ...body } }),
    });
    renderApp("/");
    await screen.findByRole("option", { name: "Español" });          // options arrive with /languages
    await userEvent.selectOptions(screen.getByLabelText("Active language"), "es");
    await waitFor(() => expect(calls.filter((c) => c.method === "PATCH").map((c) => c.body)).toEqual([{ active_language: "es" }]));
    expect(screen.getByLabelText("Active language")).toHaveValue("es");
    expect(localStorage.getItem("tutor:lang:1")).toBeNull();
  });

  it("a second device shows the language chosen on the first", async () => {
    mockApi({ "GET /me": { ...ALICE, languages: ["en", "es"], preferences: { active_language: "es", ui_follows_study_language: false, theme: "system", custom_colors: null } }, "GET /languages": LANGS, "GET /words": { items: [], total: 0, limit: 1, offset: 0 } });
    renderApp("/");
    await waitFor(() => expect(screen.getByLabelText("Active language")).toHaveValue("es"));
  });
});
