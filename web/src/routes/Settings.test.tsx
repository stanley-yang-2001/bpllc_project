import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ALICE, err, LANGS, mockApi, renderApp } from "../test/helpers";

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); localStorage.clear(); document.documentElement.classList.remove("dark"); });

const HEALTH = { postgres: { ok: true }, langflow: {}, groq: {}, ai_mode: "live" };
const base = { "GET /me": ALICE, "GET /languages": LANGS, "GET /health": HEALTH };

describe("settings: profile and email", () => {
  it("saves a new name and native language", async () => {
    const { calls } = mockApi({ ...base, "PATCH /me": ({ body }: { body: object }) => ({ json: { ...ALICE, ...body } }) });
    renderApp("/settings");
    const save = await screen.findByRole("button", { name: "Save profile" });
    expect(save).toBeDisabled();                                      // nothing changed yet
    await userEvent.clear(screen.getByLabelText("Your name"));
    await userEvent.type(screen.getByLabelText("Your name"), "Alice Smith");
    await userEvent.selectOptions(screen.getByLabelText("Native language"), "es");
    await userEvent.click(save);
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH")!.body).toEqual({ display_name: "Alice Smith", native_language: "es" }));
    expect(await screen.findByText("Profile saved")).toBeInTheDocument();
    expect(screen.getAllByText("Alice Smith").length).toBeGreaterThan(0);     // header now greets the new name
  });

  it("shows the account's email and refuses to change it with the wrong password", async () => {
    mockApi({ ...base, "POST /me/email": err(403, "wrong_password", "That password is not correct.") });
    renderApp("/settings");
    expect((await screen.findAllByText("alice@example.com")).length).toBeGreaterThan(0);
    await userEvent.type(screen.getByLabelText("New email"), "new@example.com");
    await userEvent.type(screen.getByLabelText("Current password", { selector: "#e-pass" }), "wrong");
    await userEvent.click(screen.getByRole("button", { name: "Change email" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("That password is not correct.");
    expect(screen.queryByText("new@example.com")).not.toBeInTheDocument();
  });

  it("changes the email and shows the new address", async () => {
    const { calls } = mockApi({ ...base, "POST /me/email": ({ body }: { body: { email: string } }) => ({ json: { ...ALICE, email: body.email } }) });
    renderApp("/settings");
    await userEvent.type(await screen.findByLabelText("New email"), "new@example.com");
    await userEvent.type(screen.getByLabelText("Current password", { selector: "#e-pass" }), "password123");
    await userEvent.click(screen.getByRole("button", { name: "Change email" }));
    expect(await screen.findByText("Email address changed")).toBeInTheDocument();
    expect(calls.find((c) => c.path === "/me/email")!.body).toEqual({ email: "new@example.com", password: "password123" });
    expect((await screen.findAllByText("new@example.com")).length).toBeGreaterThan(0);
  });
});

describe("settings: password", () => {
  it("won't submit until the new password is long enough and typed twice the same", async () => {
    const { calls } = mockApi({ ...base, "POST /me/password": () => ({ status: 204 }) });
    renderApp("/settings");
    const submit = await screen.findByRole("button", { name: "Change password" });
    await userEvent.type(screen.getByLabelText("Current password", { selector: "#pw-cur" }), "password123");
    await userEvent.type(screen.getByLabelText("New password"), "short");
    expect(submit).toBeDisabled();
    await userEvent.clear(screen.getByLabelText("New password"));
    await userEvent.type(screen.getByLabelText("New password"), "a-new-password");
    await userEvent.type(screen.getByLabelText("New password again"), "a-different-one");
    expect(await screen.findByText("The two new passwords don't match")).toBeInTheDocument();
    expect(submit).toBeDisabled();
    await userEvent.clear(screen.getByLabelText("New password again"));
    await userEvent.type(screen.getByLabelText("New password again"), "a-new-password");
    expect(submit).toBeEnabled();
    await userEvent.click(submit);
    expect(await screen.findByText(/other devices were logged out/)).toBeInTheDocument();
    expect(calls.find((c) => c.path === "/me/password")!.body).toEqual({ current_password: "password123", new_password: "a-new-password" });
  });
});

describe("settings: appearance", () => {
  it("choosing Dark turns dark mode on and remembers it", async () => {
    mockApi(base);
    renderApp("/settings");
    await userEvent.click(await screen.findByRole("radio", { name: "Dark" }));
    expect(document.documentElement).toHaveClass("dark");
    expect(localStorage.getItem("tutor:theme")).toBe("dark");
    await userEvent.click(screen.getByRole("radio", { name: "Light" }));
    expect(document.documentElement).not.toHaveClass("dark");
  });
});

describe("settings: your data", () => {
  it("downloads everything we hold as a JSON file", async () => {
    const payload = { profile: { email: "alice@example.com" }, words: [] };
    mockApi({ ...base, "GET /me/export": payload });
    const created: Blob[] = [];
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: (b: Blob) => { created.push(b); return "blob:x"; }, revokeObjectURL: () => {} }));
    const clicked: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) { clicked.push(this.download); });
    renderApp("/settings");
    await userEvent.click(await screen.findByRole("button", { name: "Download my data" }));
    expect(await screen.findByText("Your data was downloaded")).toBeInTheDocument();
    expect(clicked[0]).toMatch(/^language-tutor-my-data-\d{4}-\d{2}-\d{2}\.json$/);
    expect(JSON.parse(await created[0].text())).toEqual(payload);
  });

  it("links to the privacy policy and says what is kept", async () => {
    mockApi(base);
    renderApp("/settings");
    expect(await screen.findByText(/We keep your name, your email and the words you add/)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Privacy Policy" })[0]).toHaveAttribute("href", "/privacy");
  });
});

describe("settings: deleting the account", () => {
  const open = async () => {
    await userEvent.click(await screen.findByRole("button", { name: "Delete account" }));
    return within(await screen.findByRole("dialog"));
  };

  it("lists what is deleted, needs a password, and can be cancelled without any request", async () => {
    const { calls } = mockApi(base);
    renderApp("/settings");
    const dialog = await open();
    expect(dialog.getByText(/your name and email address/)).toBeInTheDocument();
    expect(dialog.getByText(/all your words, meanings and languages/)).toBeInTheDocument();
    expect(dialog.getByRole("button", { name: "Delete my account" })).toBeDisabled();       // no password yet
    await userEvent.click(dialog.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(calls.some((c) => c.path === "/me/delete")).toBe(false);
  });

  it("a wrong password keeps the account and the session", async () => {
    mockApi({ ...base, "POST /me/delete": err(403, "wrong_password", "That password is not correct.") });
    renderApp("/settings");
    const dialog = await open();
    await userEvent.type(dialog.getByLabelText("Enter your password to confirm"), "nope");
    await userEvent.click(dialog.getByRole("button", { name: "Delete my account" }));
    expect(await dialog.findByRole("alert")).toHaveTextContent("That password is not correct.");
    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();         // still logged in
  });

  it("the right password deletes the account and returns to the login page with nothing cached", async () => {
    let deleted = false;
    const { calls, fn } = mockApi({
      "GET /me": () => (deleted ? err(401, "unauthorized", "Please log in.")() : { json: ALICE }),
      "GET /languages": LANGS, "GET /health": HEALTH,
      "POST /me/delete": () => { deleted = true; return { status: 204 }; },
    });
    sessionStorage.setItem("chat", "private");
    const { client } = renderApp("/settings");
    const dialog = await open();
    await userEvent.type(dialog.getByLabelText("Enter your password to confirm"), "password123");
    await userEvent.click(dialog.getByRole("button", { name: "Delete my account" }));
    expect(await screen.findByRole("button", { name: "Log in" })).toBeInTheDocument();
    expect(calls.find((c) => c.path === "/me/delete")!.body).toEqual({ password: "password123" });
    expect(sessionStorage.getItem("chat")).toBeNull();
    expect(client.getQueryCache().findAll({ predicate: (q) => q.queryKey[0] !== "me" && q.queryKey[0] !== "languages" })).toHaveLength(0);
    void fn;
  });
});
