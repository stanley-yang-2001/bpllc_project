import { RotateCcw } from "lucide-react";
import { Button, ErrorText } from "../components/ui";
import { useI18n } from "../i18n/I18nProvider";
import { StoryTools } from "../text/StoryTools";
import type { ChatMessage } from "./ChatContext";
import { SaveStory } from "./SaveStory";
import { storyCalls } from "./storyCalls";
import { ToolTrace } from "./ToolTrace";

/** What the learner said, and, if the tutor could not be reached, the reason and a Try again button. */
export function UserBubble({ m, onRetry, disabled }: { m: ChatMessage; onRetry: () => void; disabled: boolean }) {
  const { t, code } = useI18n();
  return (
    <div className="flex flex-col items-end gap-1.5">
      <p className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-brand-600 px-3.5 py-2 text-sm text-white">{m.text}</p>
      {m.error && (
        <div className="flex flex-col items-end">
          <ErrorText>{code(m.errorCode, m.error)}</ErrorText>
          <Button variant="ghost" className="mt-1" icon={<RotateCcw aria-hidden className="size-4" />} onClick={onRetry} disabled={disabled}>
            {t("common.tryAgain")}
          </Button>
        </div>
      )}
    </div>
  );
}

/** The tutor's reply, what it did behind the scenes, and for each story it wrote: the text tools and Save. */
export function TutorBubble({ m }: { m: ChatMessage }) {
  return (
    <div className="flex flex-col items-start">
      <p className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-bl-md border border-slate-200 bg-slate-50 px-3.5 py-2 text-sm text-slate-900 dark:bg-slate-100/40">{m.text}</p>
      <div className="max-w-[85%] self-stretch">
        <ToolTrace calls={m.toolCalls} />
        {m.language && storyCalls(m.toolCalls).map((c, i) => (
          <div key={i} className="mt-2 space-y-2"><StoryTools text={c.output} language={m.language!} id={`chat-${m.id}-${i}`} /><SaveStory call={c} language={m.language!} /></div>
        ))}
      </div>
    </div>
  );
}
