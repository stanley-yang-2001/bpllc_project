import { MessageCircle } from "lucide-react";
import { useEffect, useRef } from "react";
import { EmptyState } from "../components/ui";
import { useI18n } from "../i18n/I18nProvider";
import { TutorBubble, UserBubble } from "./Bubbles";
import type { ChatMessage } from "./ChatContext";
import { Waiting } from "./Waiting";

/** The scrolling log: an empty state, the messages in order, and the waiting line while the tutor works. */
export function Conversation({ messages, sending, languageName, onRetry }: { messages: ChatMessage[]; sending: boolean; languageName: string; onRetry: (id: number) => void }) {
  const { t } = useI18n();
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView?.({ block: "end" }); }, [messages, sending]);
  return (
    <div role="log" aria-label={t("chat.conversation")} aria-live="polite" className="min-h-64 space-y-4">
      {messages.length === 0 && !sending && (
        <EmptyState icon={<MessageCircle aria-hidden className="size-5" />} title={t("chat.empty.title")}>
          {t("chat.empty.body", { language: languageName })}
        </EmptyState>
      )}
      {messages.map((m) => m.role === "user"
        ? <UserBubble key={m.id} m={m} onRetry={() => onRetry(m.id)} disabled={sending} />
        : <TutorBubble key={m.id} m={m} />)}
      {sending && <Waiting />}
      <div ref={end} />
    </div>
  );
}
