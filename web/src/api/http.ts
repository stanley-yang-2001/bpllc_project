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

export interface Opts { json?: unknown; form?: FormData; skipExpected?: boolean }

export async function request<T>(method: string, path: string, opts: Opts = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (currentUserId !== null && !opts.skipExpected) headers["X-Expected-User"] = String(currentUserId);
  let body: BodyInit | undefined;
  if (method !== "GET") headers["X-Requested-With"] = "tutor"; // CSRF defence: the API rejects non-GET without it
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
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const e = data?.error;
    throw new ApiError(res.status, e?.code ?? "error", e?.message ?? `Request failed (${res.status})`, e?.retry_after);
  }
  return data as T;
}

export const qs = (params: Record<string, string | number | undefined>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") p.set(k, String(v));
  return p.toString();
};
