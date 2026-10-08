import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./client";
import { mockApi } from "../test/helpers";

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("sends the CSRF header on writes but not on reads", async () => {
    const { calls } = mockApi({ "GET /me": { id: 1 }, "POST /words/delete": { deleted: 1 } });
    await api.me();
    await api.deleteWords([1]);
    expect(calls[0].headers["X-Requested-With"]).toBeUndefined();
    expect(calls[1].headers["X-Requested-With"]).toBe("tutor");
    expect(calls[1].body).toEqual({ ids: [1] });
  });

  it("turns the API error body into an ApiError", async () => {
    mockApi({ "POST /auth/login": () => ({ status: 429, json: { error: { code: "login_locked", message: "Too many", retry_after: 30 } } }) });
    const e = await api.login({ email: "a@example.com", password: "b" }).catch((x) => x);
    expect(e).toBeInstanceOf(ApiError);
    expect(e).toMatchObject({ status: 429, code: "login_locked", message: "Too many", retryAfter: 30 });
  });

  it("reports an unreachable server clearly", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));
    await expect(api.me()).rejects.toMatchObject({ code: "network_error", status: 0 });
  });

  it("handles 204 and builds the words query string without empty params", async () => {
    const { calls } = mockApi({ "POST /auth/logout": () => ({ status: 204 }), "GET /words": { items: [], total: 0, limit: 50, offset: 0 } });
    await expect(api.logout()).resolves.toBeUndefined();
    await api.words({ language: "es", q: "", limit: 50, offset: 0 });
    expect(calls[1].path).toBe("/words?language=es&limit=50&offset=0");
  });

  it("uploads the language and file as multipart form data", async () => {
    const { calls } = mockApi({ "POST /words/upload": { added: 1, duplicates: 0, invalid_count: 0, invalid: [] } });
    await api.uploadWords("es", new File(["word\nagua\n"], "w.csv", { type: "text/csv" }));
    expect(calls[0].body.language).toBe("es");
    expect(calls[0].body.file).toBeInstanceOf(File);
  });
});
