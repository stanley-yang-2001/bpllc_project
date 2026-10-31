import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type User } from "../api/client";
import type { Prefs } from "./deviceCopy";

const SAVE_DELAY_MS = 600;

export type Overrides = { userId: number | null; values: Partial<Prefs> };

/**
 * Saving: changes apply at once as overrides and go to the account after a short pause, one request at a time.
 * It knows nothing about defaults, the device copy or old settings; the provider merges what it returns.
 */
export function useSavedPreferences(userId: number | null) {
  const qc = useQueryClient();
  const [overrides, setOverrides] = useState<Overrides>({ userId: null, values: {} });
  const [saveFailed, setSaveFailed] = useState(false);
  const pending = useRef<Partial<Prefs>>({});
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const inflight = useRef(false);
  const again = useRef(false);
  const owner = useRef<number | null>(userId);
  owner.current = userId;

  // Another person, or nobody: an unsaved change of the previous person must never be saved into this account.
  useEffect(() => {
    pending.current = {};
    again.current = false;
    if (timer.current) { clearTimeout(timer.current); timer.current = undefined; }
    setOverrides({ userId: null, values: {} });
    setSaveFailed(false);
  }, [userId]);

  const flush = useCallback(async (): Promise<boolean> => {
    if (timer.current) { clearTimeout(timer.current); timer.current = undefined; }
    if (inflight.current) { again.current = true; return false; }
    const batch = pending.current;
    const who = owner.current;
    if (who === null || Object.keys(batch).length === 0) return true;
    pending.current = {};
    inflight.current = true;
    let ok = false;
    try {
      const saved = await api.savePreferences(batch);
      if (owner.current !== who) return false;
      qc.setQueryData<User | null>(["me"], (me) => (me && me.id === who ? { ...me, preferences: saved } : me));
      // Keep a local value only if it changed again after this request left.
      setOverrides((o) => {
        if (o.userId !== who) return o;
        const values: Partial<Prefs> = { ...o.values };
        for (const k of Object.keys(batch) as (keyof Prefs)[]) if (!(k in pending.current)) delete values[k];
        return { userId: who, values };
      });
      setSaveFailed(false);
      ok = true;
    } catch {
      if (owner.current === who) {
        pending.current = { ...batch, ...pending.current };      // newer values win; the next change retries the lot
        setSaveFailed(true);
      }
    } finally {
      inflight.current = false;
      if (again.current) { again.current = false; void flush(); }
    }
    return ok;
  }, [qc]);

  /** Applies at once and saves after a short pause (or at once with `now`). Resolves to whether the save worked. */
  const update = useCallback((changes: Partial<Prefs>, opts?: { now?: boolean }): Promise<boolean> => {
    const who = owner.current;
    if (who === null) return Promise.resolve(false);
    pending.current = { ...pending.current, ...changes };
    setOverrides((o) => ({ userId: who, values: { ...(o.userId === who ? o.values : {}), ...changes } }));
    if (opts?.now) return flush();
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => { void flush(); }, SAVE_DELAY_MS);
    return Promise.resolve(true);
  }, [flush]);

  return { overrides, update, saveFailed };
}
