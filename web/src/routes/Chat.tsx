import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BookmarkPlus, LoaderCircle, MessageCircle, RotateCcw, SendHorizontal, SquarePen } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, type ToolCall } from "../api/client";
import { storiesKey } from "../api/keys";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { useAuth } from "../auth/AuthContext";
import { MAX_CHARS, SLOW_AFTER_MS, useChat } from "../chat/ChatContext";
import { ToolTrace } from "../chat/ToolTrace";
import { useToast } from "../components/Toast";
import { Badge, Button, Card, EmptyState, ErrorText, inputCls, Notice, PageHeader } from "../components/ui";

const STORY_TOOL = "Story Generator Tool";
const NOT_A_STORY = /not available yet|having trouble/i;          // the tool's own refusal messages

/** Offers to keep a story the tutor wrote. The API makes the quality report when it saves; the chat itself is not stored. */
function SaveStory({ call, language }: { call: ToolCall; language: string }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const save = useMutation({
    mutationFn: () => api.saveStory({ language, body: call.output, story_type: null, topic: null }),
    onSuccess: () => { toast("Saved to your library"); if (user) void qc.invalidateQueries({ queryKey: storiesKey(user.id) }); },
  });
  return (
    <div className="mt-2">
      <Button variant="secondary" onClick={() => save.mutate()} disabled={save.isSuccess} loading={save.isPending} icon={<BookmarkPlus aria-hidden className="size-4" />}>
        {save.isSuccess ? "Saved" : "Save story to library"}
      </Button>
      {save.error && <ErrorText>{save.error instanceof ApiError ? save.error.message : "Couldn't save. Please try again."}</ErrorText>}
    </div>
  );
}

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
                <div className="max-w-[85%] self-stretch">
                  <ToolTrace calls={m.toolCalls} />
                  {m.language && m.toolCalls.filter((c) => c.name === STORY_TOOL && !c.failed && c.output.trim() && !NOT_A_STORY.test(c.output)).map((c, i) => (
                    <SaveStory key={i} call={c} language={m.language!} />
                  ))}
                </div>
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
