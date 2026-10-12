import { LoaderCircle, MessageCircle, RotateCcw, SendHorizontal, SquarePen } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { MAX_CHARS, SLOW_AFTER_MS, useChat } from "../chat/ChatContext";
import { ToolTrace } from "../chat/ToolTrace";
import { Badge, Button, Card, EmptyState, ErrorText, inputCls, Notice, PageHeader } from "../components/ui";

function Waiting() {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    return () => clearTimeout(t);
  }, []);
  return (
    <p role="status" className="flex items-center gap-2 text-sm text-slate-600">
      <LoaderCircle aria-hidden className="size-4 animate-spin" />
      {slow ? "Still working. Stories can take up to a minute." : "The tutor is thinking…"}
    </p>
  );
}

export default function Chat() {
  const { active, info } = useActiveLanguage();
  const { messages, sending, send, retry, newChat } = useChat();
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const name = info(active)?.name ?? active;

  useEffect(() => { end.current?.scrollIntoView?.({ block: "end" }); }, [messages, sending]);

  const submit = () => {
    if (!text.trim() || sending) return;
    send(text, active);
    setText("");
  };

  return (
    <div>
      <PageHeader
        title="Chat"
        description="Ask the tutor to add words to your vocabulary or write you a short story."
        actions={
          <div className="flex items-center gap-2">
            <Badge tone="brand">{name}</Badge>
            <Button variant="secondary" icon={<SquarePen aria-hidden className="size-4" />} onClick={newChat} disabled={sending || messages.length === 0}>
              New chat
            </Button>
          </div>
        }
      />

      <Card className="flex flex-col gap-4">
        <div role="log" aria-label="Conversation" aria-live="polite" className="min-h-64 space-y-4">
          {messages.length === 0 && !sending && (
            <EmptyState icon={<MessageCircle aria-hidden className="size-5" />} title="Start a conversation">
              Try “add the word bread” to add a word to your vocabulary, or “tell me a story” for a short dialogue. Words you add go to your {name} list.
            </EmptyState>
          )}
          {messages.map((m) =>
            m.role === "user" ? (
              <div key={m.id} className="flex flex-col items-end gap-1.5">
                <p className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-brand-600 px-3.5 py-2 text-sm text-white">{m.text}</p>
                {m.error && (
                  <div className="flex flex-col items-end">
                    <ErrorText>{m.error}</ErrorText>
                    <Button variant="ghost" className="mt-1" icon={<RotateCcw aria-hidden className="size-4" />} onClick={() => retry(m.id, active)} disabled={sending}>
                      Try again
                    </Button>
                  </div>
                )}
              </div>
            ) : (
              <div key={m.id} className="flex flex-col items-start">
                <p className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-bl-md border border-slate-200 bg-slate-50 px-3.5 py-2 text-sm text-slate-900 dark:bg-slate-100/40">{m.text}</p>
                <div className="max-w-[85%] self-stretch"><ToolTrace calls={m.toolCalls} /></div>
              </div>
            ),
          )}
          {sending && <Waiting />}
          <div ref={end} />
        </div>

        <div>
          <label htmlFor="chat-message" className="sr-only">Message</label>
          <div className="flex items-end gap-2">
            <textarea
              id="chat-message"
              aria-label="Message"
              className={`${inputCls} resize-none`}
              rows={2}
              maxLength={MAX_CHARS}
              placeholder={`Message the tutor (Enter to send, Shift+Enter for a new line)`}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {   // Enter also confirms an input-method choice
                  e.preventDefault();
                  submit();
                }
              }}
            />
            <Button onClick={submit} disabled={sending || !text.trim()} icon={<SendHorizontal aria-hidden className="size-4" />}>
              Send
            </Button>
          </div>
          <p className="mt-2 text-xs text-slate-600">The tutor is an AI and can make mistakes. Don't share personal details in chat.</p>
        </div>
      </Card>
      <div className="mt-4"><Notice>This conversation is kept only on this page. It is gone when you log out or close the tab.</Notice></div>
    </div>
  );
}
