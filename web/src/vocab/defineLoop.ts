import { api, type SetFilter } from "../api/client";

/** Asks the tutor for meanings, 25 words per request, until none are left. Stops if a request writes nothing, so it cannot loop. */
export async function defineLoop(base: { language: string; ids?: number[]; set?: SetFilter }, onProgress: (done: number, left: number) => void) {
  let done = 0, failed = 0, remaining = 1;
  while (remaining > 0) {
    const r = await api.defineWords(base);
    done += r.defined; failed += r.failed; remaining = r.remaining;
    onProgress(done, remaining);
    if (r.defined === 0) break;
  }
  return { done, failed, remaining };
}
