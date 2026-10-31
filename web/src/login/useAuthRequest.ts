import { useState } from "react";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";

/** Runs a login or sign-up call, signs the learner in on success and keeps the server's message when it fails. */
export function useAuthRequest() {
  const { setUser } = useAuth();
  const [serverError, setServerError] = useState<string>();
  const run = async (call: () => Promise<unknown>) => {
    setServerError(undefined);
    try {
      setUser((await call()) as Parameters<typeof setUser>[0]);
    } catch (e) {
      setServerError(e instanceof ApiError ? e.message : "Something went wrong.");
    }
  };
  return { serverError, run, clearError: () => setServerError(undefined) };
}
