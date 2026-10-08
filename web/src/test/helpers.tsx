import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import App from "../App";
import { AuthProvider } from "../auth/AuthContext";
import { ThemeProvider } from "../theme/ThemeProvider";

export type Handler = (req: { method: string; path: string; body: any; headers: Record<string, string> }) => { status?: number; json?: unknown; after?: Promise<unknown> };

/** Route-table fetch mock: key is "METHOD /path" (query string ignored unless the key includes it). */
export function mockApi(routes: Record<string, Handler | unknown>) {
  const calls: { method: string; path: string; body: any; headers: Record<string, string> }[] = [];
  const fn = vi.fn(async (url: string, init: RequestInit = {}) => {
    const method = (init.method ?? "GET").toUpperCase();
    const path = url.replace(/^\/api/, "");
    const bare = path.split("?")[0];
    let body: any = undefined;
    if (typeof init.body === "string") body = JSON.parse(init.body);
    else if (init.body instanceof FormData) body = Object.fromEntries(init.body.entries());
    const call = { method, path, body, headers: (init.headers ?? {}) as Record<string, string> };
    calls.push(call);
    const entry = routes[`${method} ${path}`] ?? routes[`${method} ${bare}`];
    if (entry === undefined) return new Response(JSON.stringify({ error: { code: "not_found", message: `no mock for ${method} ${path}` } }), { status: 404 });
    const out = typeof entry === "function" ? (entry as Handler)(call) : { json: entry };
    if (out.after) await out.after;                 // lets a test hold a response back (slow network)
    const status = out.status ?? 200;
    return new Response(status === 204 ? null : JSON.stringify(out.json ?? {}), { status });
  });
  vi.stubGlobal("fetch", fn);
  return { calls, fn };
}

export const LANGS = [
  { code: "en", name: "English", native: "English", tier: 1, stories_enabled: true },
  { code: "es", name: "Spanish", native: "Español", tier: 1, stories_enabled: true },
];
export const ALICE = { id: 1, email: "alice@example.com", display_name: "Alice", native_language: "en", languages: ["en"] };
export const BOB = { id: 2, email: "bob@example.com", display_name: "Bob", native_language: "en", languages: ["en"] };
export const err = (status: number, code: string, message: string) => () => ({ status, json: { error: { code, message } } });

export function renderApp(path = "/", client = new QueryClient({ defaultOptions: { queries: { retry: false } } })): { ui: ReturnType<typeof render>; client: QueryClient } {
  const ui: ReactElement = (
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <AuthProvider>
          <MemoryRouter initialEntries={[path]}>
            <App />
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
  return { ui: render(ui), client };
}
