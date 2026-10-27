import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { api, ApiError, type ToolCall } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export const MAX_CHARS = 2000;        // the API refuses longer messages
export const SLOW_AFTER_MS = 8000;    // after this the page says the tutor is still working (the API gives up at ~100 s)

export interface ChatMessage {
  id: number;
  role: "user" | "tutor";
  text: string;
  toolCalls: ToolCall[];
  language?: string;                  // on a tutor message: the language the learner was in when it was asked
  error?: string;                     // the server's message (English)
  errorCode?: string;                 // its code: the screen translates by code when it can
}

interface Value {
  messages: ChatMessage[];
  sending: boolean;
  send: (text: string, language: string, setIds?: number[]) => void;
  retry: (id: number, language: string, setIds?: number[]) => void;
  newChat: () => void;
}
const Ctx = createContext<Value | null>(null);

/** 32 random hex characters. The API puts the user's id in front of it, so this alone can never name another
 * learner's conversation. */
export function newSessionId(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

/** The conversation lives in memory only: nothing is written to localStorage, sessionStorage or the URL. It is mounted
 * under ProtectedLayout (keyed by user id), so a different learner on the same browser always starts empty. */
export function ChatProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const { user, setUser } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  const busy = useRef(false);                        // the synchronous guard: state updates arrive a render too late
  const nextId = useRef(1);
  const session = useRef(newSessionId());
  const userId = user?.id;
  // Through a mutation, not a bare fetch: AuthProvider watches the mutation cache for a 401 (session ended, or another
  // tab logged in as someone else) and then drops this learner's data and adopts whoever is signed in now.
  const chatCall = useMutation({ mutationFn: api.chat });
  const chatRef = useRef(chatCall.mutateAsync);
  chatRef.current = chatCall.mutateAsync;

  const run = useCallback(
    async (id: number, text: string, language: string, setIds?: number[]) => {
      busy.current = true;
      setSending(true);
      try {
        const r = await chatRef.current({ message: text, language, session_id: session.current, ...(setIds ? { set_ids: setIds } : {}) });
        setMessages((m) => [
          ...m.map((x) => (x.id === id ? { ...x, error: undefined, errorCode: undefined } : x)),
          { id: nextId.current++, role: "tutor", text: r.reply, toolCalls: r.tool_calls, language },
        ]);
        if (r.tool_calls.some((c) => c.name === "Add Word" && !c.failed) && userId !== undefined) {
          void qc.invalidateQueries({ queryKey: ["words", userId] });       // the Vocabulary page and Home's word count
          void api.me().then(setUser).catch(() => undefined);               // adding a word can add a language
        }
      } catch (e) {
        const message = e instanceof ApiError ? e.message : "Something went wrong. Please try again.";
        const errorCode = e instanceof ApiError ? e.code : undefined;
        setMessages((m) => m.map((x) => (x.id === id ? { ...x, error: message, errorCode } : x)));
      } finally {
        busy.current = false;
        setSending(false);
      }
    },
    [qc, setUser, userId],
  );

  const send = useCallback(
    (raw: string, language: string, setIds?: number[]) => {
      const text = raw.trim();
      if (!text || busy.current) return;
      const id = nextId.current++;
      setMessages((m) => [...m, { id, role: "user", text, toolCalls: [] }]);
      void run(id, text, language, setIds);
    },
    [run],
  );

  const retry = useCallback(
    (id: number, language: string, setIds?: number[]) => {
      if (busy.current) return;
      const original = messages.find((m) => m.id === id);
      if (!original) return;
      setMessages((m) => m.map((x) => (x.id === id ? { ...x, error: undefined } : x)));
      void run(id, original.text, language, setIds);
    },
    [messages, run],
  );

  const newChat = useCallback(() => {
    if (busy.current) return;
    session.current = newSessionId();
    setMessages([]);
  }, []);

  const value = useMemo(() => ({ messages, sending, send, retry, newChat }), [messages, sending, send, retry, newChat]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useChat(): Value {
  const v = useContext(Ctx);
  if (!v) throw new Error("useChat must be used inside <ChatProvider>");
  return v;
}
