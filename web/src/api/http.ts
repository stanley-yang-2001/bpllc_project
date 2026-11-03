/** The one place that talks to the API: the error type, the request helper and the query-string helper. */
/** Every non-2xx response from the API has the same body: {error: {code, message, retry_after?}}. */
export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public retryAfter?: number) {
    super(message);
  }
}

/** The id of the user this tab is showing. Sent with every request so that, if someone else logs in on another
 * tab (browsers share one cookie across tabs), this tab is refused instead of acting as the wrong person. */
let currentUserId: number | null = null;
export const setCurrentUserId = (id: number | null) => { currentUserId = id; };

export interface Opts { json?: unknown; form?: FormData; skipExpected?: boolean; onDelta?: (text: string) => void }

export async function request<T>(method: string, path: string, opts: Opts = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (currentUserId !== null && !opts.skipExpected) headers["X-Expected-User"] = String(currentUserId);
  let body: BodyInit | undefined;
  if (method !== "GET") headers["X-Requested-With"] = "tutor"; // CSRF defence: the API rejects non-GET without it
  if (opts.onDelta) headers["Accept"] = "application/x-ndjson, application/json"; // the API streams only when it is switched on; otherwise it answers with one JSON body
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  } else if (opts.form) {
    body = opts.form;
  }
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { method, headers, body, credentials: "same-origin" });
  } catch {
    throw new ApiError(0, "network_error", "Can't reach the server. Is it running?");
  }
  if (res.status === 204) return undefined as T;
  if (res.ok && opts.onDelta && (res.headers.get("content-type") ?? "").includes("application/x-ndjson")) return readStream<T>(res, opts.onDelta);
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const e = data?.error;
    throw new ApiError(res.status, e?.code ?? "error", e?.message ?? `Request failed (${res.status})`, e?.retry_after);
  }
  return data as T;
}

/** The answer as lines of JSON: {event:"delta", text} while the tutor writes, then one {event:"final", ...answer} or {event:"error", status, error}. */
async function readStream<T>(res: Response, onDelta: (text: string) => void): Promise<T> {
  const reader = res.body?.getReader();
  if (!reader) throw new ApiError(0, "network_error", "Can't reach the server. Is it running?");
  const decoder = new TextDecoder();
  let pending = "";
  let final: T | undefined;
  const handle = (line: string) => {
    if (!line.trim()) return;
    let e: { event?: string; text?: string; status?: number; error?: { code?: string; message?: string; retry_after?: number } } & Record<string, unknown>;
    try { e = JSON.parse(line); } catch { return; }
    if (e.event === "delta" && typeof e.text === "string") onDelta(e.text);
    else if (e.event === "final") { const { event: _event, ...rest } = e; final = rest as T; }
    else if (e.event === "error") throw new ApiError(e.status ?? 500, e.error?.code ?? "error", e.error?.message ?? "Something went wrong. Please try again.", e.error?.retry_after ?? undefined);
  };
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      pending += decoder.decode(value, { stream: true });
      const parts = pending.split("\n");
      pending = parts.pop() ?? "";
      parts.forEach(handle);
    }
    handle(pending + decoder.decode());
  } catch (e) {
    if (e instanceof ApiError) throw e;
    throw new ApiError(0, "network_error", "Can't reach the server. Is it running?");
  }
  if (final === undefined) throw new ApiError(0, "network_error", "The answer was cut off. Please try again.");
  return final;
}

export const qs = (params: Record<string, string | number | undefined>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") p.set(k, String(v));
  return p.toString();
};
