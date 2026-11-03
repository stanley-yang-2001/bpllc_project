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

  describe("streamed chat answers", () => {
    const stream = (parts: string[], type = "application/x-ndjson") => {
      const enc = new TextEncoder();
      return new Response(new ReadableStream({ start(c) { parts.forEach((p) => c.enqueue(enc.encode(p))); c.close(); } }), { status: 200, headers: { "content-type": type } });
    };
    const body = { message: "hi", language: "es", session_id: "a".repeat(32) };

    it("asks for a stream, passes the words on as they come (even split across chunks) and returns the final answer", async () => {
      const fetchMock = vi.fn().mockResolvedValue(stream(['{"event":"delta","text":"Ho"}\n{"event":"del', 'ta","text":"la"}\n', '{"event":"final","reply":"Hola","tool_calls":[],"session_id":"s","notice":null}\n']));
      vi.stubGlobal("fetch", fetchMock);
      const seen: string[] = [];
      const r = await api.chat(body, (t) => seen.push(t));
      expect(seen).toEqual(["Ho", "la"]);
      expect(r).toMatchObject({ reply: "Hola", session_id: "s" });
      expect("event" in (r as object)).toBe(false);
      expect(fetchMock.mock.calls[0][1].headers.Accept).toContain("application/x-ndjson");
    });

    it("reads a plain JSON answer when the API does not stream", async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ reply: "Hola", tool_calls: [], session_id: "s" }), { status: 200, headers: { "content-type": "application/json" } })));
      const seen: string[] = [];
      expect((await api.chat(body, (t) => seen.push(t))).reply).toBe("Hola");
      expect(seen).toEqual([]);
    });

    it("turns an error line into the usual ApiError", async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(stream(['{"event":"delta","text":"Ho"}\n{"event":"error","status":429,"error":{"code":"tutor_busy","message":"Busy","retry_after":15}}\n'])));
      await expect(api.chat(body, () => undefined)).rejects.toMatchObject({ status: 429, code: "tutor_busy", message: "Busy", retryAfter: 15 });
    });

    it("says so when the stream ends without an answer", async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(stream(['{"event":"delta","text":"Ho"}\n'])));
      await expect(api.chat(body, () => undefined)).rejects.toMatchObject({ code: "network_error" });
    });
  });
});
