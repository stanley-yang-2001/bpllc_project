import { useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, type ReactNode } from "react";
import { api, ApiError, setCurrentUserId, type User } from "../api/client";

interface AuthValue {
  user: User | null;
  loading: boolean;
  setUser: (u: User) => void;
  logout: () => Promise<void>;
  logoutAll: () => Promise<void>;
  /** Permanently deletes the account. Rejects (and keeps the session) if the password is wrong. */
  deleteAccount: (password: string) => Promise<void>;
}
const Ctx = createContext<AuthValue | null>(null);

const dropPrivateData = (qc: QueryClient) => qc.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" });

/** Forget everything shown for the current person, then ask the server who is *really* signed in.
 * "me" goes to null first so nothing of the previous person stays on screen while we find out. */
export function resync(qc: QueryClient) {
  setCurrentUserId(null);
  sessionStorage.clear();
  qc.setQueryData(["me"], null);
  dropPrivateData(qc);
  void qc.invalidateQueries({ queryKey: ["me"] });
}

const isAuthFailure = (e: unknown) =>
  e instanceof ApiError && e.status === 401 && (e.code === "unauthorized" || e.code === "session_changed");

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const channel = useRef<BroadcastChannel | null>(null);

  const { data, isPending } = useQuery({
    queryKey: ["me"],
    retry: false,
    staleTime: Infinity,
    queryFn: async () => {
      try {
        const me = await api.me();
        setCurrentUserId(me.id);
        return me;
      } catch (e) {
        setCurrentUserId(null);
        if (e instanceof ApiError && e.status === 401) return null; // not logged in is a normal state
        throw e;
      }
    },
  });

  // Other tabs share our cookie. Tell them when the login changes, and listen for theirs.
  useEffect(() => {
    if (typeof BroadcastChannel === "undefined") return;
    const ch = new BroadcastChannel("tutor-auth");
    channel.current = ch;
    ch.onmessage = () => resync(qc);
    return () => { ch.close(); channel.current = null; };
  }, [qc]);
  const announce = useCallback(() => channel.current?.postMessage("changed"), []);

  // A 401 from anywhere (session ended, or another tab logged in as someone else) means: stop showing this
  // person's data and find out who is signed in now.
  useEffect(() => {
    let busy = false;
    const handle = (error: unknown) => {
      if (busy || !isAuthFailure(error)) return;
      busy = true;
      resync(qc);
      setTimeout(() => { busy = false; }, 500);
    };
    const stopQueries = qc.getQueryCache().subscribe((e) => { if (e.type === "updated" && e.action.type === "error") handle(e.action.error); });
    const stopMutations = qc.getMutationCache().subscribe((e) => { if (e.type === "updated" && e.action.type === "error") handle(e.action.error); });
    return () => { stopQueries(); stopMutations(); };
  }, [qc]);

  const setUser = useCallback((u: User) => {
    const previous = qc.getQueryData<User | null>(["me"]);
    if (previous?.id !== u.id) dropPrivateData(qc);        // logging in over someone else's screen: start clean
    setCurrentUserId(u.id);
    qc.setQueryData(["me"], u);
    announce();
  }, [qc, announce]);

  // Drop everything cached for this learner and their per-session state so the next person on this
  // browser never sees it. Not qc.clear(): that detaches the "me" query from this provider.
  const forgetEverything = useCallback(() => {
    setCurrentUserId(null);
    sessionStorage.clear();
    qc.setQueryData(["me"], null);
    dropPrivateData(qc);
    announce();
  }, [qc, announce]);

  const endSession = useCallback((call: () => Promise<void>) => async () => {
    try {
      await call();
    } finally {
      forgetEverything();      // even if the request failed: logging out must always clear this screen
    }
  }, [forgetEverything]);
  const logout = useMemo(() => endSession(api.logout), [endSession]);
  const logoutAll = useMemo(() => endSession(api.logoutAll), [endSession]);
  const deleteAccount = useCallback(async (password: string) => {
    await api.deleteAccount(password);   // a wrong password throws here and nothing is cleared
    forgetEverything();
  }, [forgetEverything]);

  const value = useMemo<AuthValue>(
    () => ({ user: data ?? null, loading: isPending, setUser, logout, logoutAll, deleteAccount }),
    [data, isPending, setUser, logout, logoutAll, deleteAccount],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth must be used inside <AuthProvider>");
  return v;
}
