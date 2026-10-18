import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BookmarkPlus, LoaderCircle, MessageCircle, RotateCcw, SendHorizontal, SquarePen } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, type ToolCall } from "../api/client";
import { storiesKey } from "../api/keys";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { useAuth } from "../auth/AuthContext";
import { MAX_CHARS, SLOW_AFTER_MS, useChat } from "../chat/ChatContext";
import { ToolTrace } from "../chat/ToolTrace";
import { useToast } from "../components/Toast";
import { useI18n } from "../i18n/I18nProvider";
import { Badge, Button, Card, EmptyState, ErrorText, inputCls, Notice, PageHeader } from "../components/ui";

const STORY_TOOL = "Story Generator Tool";
const NOT_A_STORY = /not available yet|having trouble/i;          // the tool's own refusal messages

/** Offers to keep a story the tutor wrote. The API makes the quality report when it saves; the chat itself is not stored. */
function SaveStory({ call, language }: { call: ToolCall; language: string }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const { t, err } = useI18n();
  const save = useMutation({
    mutationFn: () => api.saveStory({ language, body: call.output, story_type: null, topic: null }),
    onSuccess: () => { toast(t("common.savedToLibrary")); if (user) void qc.invalidateQueries({ queryKey: storiesKey(user.id) }); },
  });
  return (
    <div className="mt-2">
      <Button variant="secondary" onClick={() => save.mutate()} disabled={save.isSuccess} loading={save.isPending} icon={<BookmarkPlus aria-hidden className="size-4" />}>
        {save.isSuccess ? t("chat.saved") : t("chat.saveStory")}
      </Button>
      {save.error && <ErrorText>{err(save.error, "common.saveFailed")}</ErrorText>}
    </div>
  );
}

function Waiting() {
  const { t } = useI18n();
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    return () => clearTimeout(t);
  }, []);
  return (
    <p role="status" className="flex items-center gap-2 text-sm text-slate-600">
      <LoaderCircle aria-hidden className="size-4 animate-spin" />
      {slow ? t("chat.slow") : t("chat.thinking")}
    </p>
  );
}

export default function Chat() {
  const { active, info } = useActiveLanguage();
  const { t, code } = useI18n();
  const { messages, sending, send, retry, newChat } = useChat();
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const name = info(active)?.native ?? active;

  useEffect(() => { end.current?.scrollIntoView?.({ block: "end" }); }, [messages, sending]);

  const submit = () => {
    if (!text.trim() || sending) return;
    send(text, active);
    setText("");
  };

  return (
    <div>
      <PageHeader
        title={t("nav.chat")}
        description={t("chat.description")}
        actions={
          <div className="flex items-center gap-2">
            <Badge tone="brand"><span lang={active}>{name}</span></Badge>
            <Button variant="secondary" icon={<SquarePen aria-hidden className="size-4" />} onClick={newChat} disabled={sending || messages.length === 0}>
              {t("chat.newChat")}
            </Button>
          </div>
        }
      />

      <Card className="flex flex-col gap-4">
        <div role="log" aria-label={t("chat.conversation")} aria-live="polite" className="min-h-64 space-y-4">
          {messages.length === 0 && !sending && (
            <EmptyState icon={<MessageCircle aria-hidden className="size-5" />} title={t("chat.empty.title")}>
              {t("chat.empty.body", { language: name })}
            </EmptyState>
          )}
          {messages.map((m) =>
            m.role === "user" ? (
              <div key={m.id} className="flex flex-col items-end gap-1.5">
                <p className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-brand-600 px-3.5 py-2 text-sm text-white">{m.text}</p>
                {m.error && (
                  <div className="flex flex-col items-end">
                    <ErrorText>{code(m.errorCode, m.error)}</ErrorText>
                    <Button variant="ghost" className="mt-1" icon={<RotateCcw aria-hidden className="size-4" />} onClick={() => retry(m.id, active)} disabled={sending}>
                      {t("common.tryAgain")}
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
          <label htmlFor="chat-message" className="sr-only">{t("chat.message")}</label>
          <div className="flex items-end gap-2">
            <textarea
              id="chat-message"
              aria-label={t("chat.message")}
              className={`${inputCls} resize-none`}
              rows={2}
              maxLength={MAX_CHARS}
              placeholder={t("chat.placeholder")}
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
              {t("common.send")}
            </Button>
          </div>
          <p className="mt-2 text-xs text-slate-600">{t("chat.disclaimer")}</p>
        </div>
      </Card>
      <div className="mt-4"><Notice>{t("chat.notice")}</Notice></div>
    </div>
  );
}
