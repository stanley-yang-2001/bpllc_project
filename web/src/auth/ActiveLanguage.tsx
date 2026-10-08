import { useQuery } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { api, type LanguageInfo } from "../api/client";
import { useAuth } from "./AuthContext";

interface Value {
  active: string;
  setActive: (code: string) => void;
  all: LanguageInfo[];
  studying: LanguageInfo[];
  info: (code: string) => LanguageInfo | undefined;
}
const Ctx = createContext<Value | null>(null);
const key = (userId: number) => `tutor:lang:${userId}`; // per learner, so two people on one browser don't share it

export function ActiveLanguageProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const { data: all = [] } = useQuery({ queryKey: ["languages"], queryFn: api.languages, staleTime: Infinity });
  const [chosen, setChosen] = useState<string | null>(() => (user ? localStorage.getItem(key(user.id)) : null));

  const mine = user?.languages ?? [];
  const studying = useMemo(() => all.filter((l) => mine.includes(l.code)), [all, mine]);
  // Fall back to the first language the learner studies if the remembered one is gone or missing.
  const active = chosen && mine.includes(chosen) ? chosen : (mine[0] ?? "en");

  const setActive = useCallback(
    (code: string) => {
      setChosen(code);
      if (user) localStorage.setItem(key(user.id), code);
    },
    [user],
  );
  const info = useCallback((code: string) => all.find((l) => l.code === code), [all]);
  return <Ctx.Provider value={{ active, setActive, all, studying, info }}>{children}</Ctx.Provider>;
}

export function useActiveLanguage(): Value {
  const v = useContext(Ctx);
  if (!v) throw new Error("useActiveLanguage must be used inside <ActiveLanguageProvider>");
  return v;
}
