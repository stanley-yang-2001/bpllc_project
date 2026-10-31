import { SquarePen } from "lucide-react";
import { useEffect, useState } from "react";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { useChat } from "../chat/ChatContext";
import { Composer } from "../chat/Composer";
import { Conversation } from "../chat/Conversation";
import { setIdsToSend, type SetChoice } from "../components/SetPicker";
import { Badge, Button, Card, Notice, PageHeader } from "../components/ui";
import { useI18n } from "../i18n/I18nProvider";

/** The chat page: the header, the conversation and the composer. The bubbles, waiting line, save button and composer are in chat/. */
export default function Chat() {
  const { active, info } = useActiveLanguage();
  const { t } = useI18n();
  const { messages, sending, send, retry, newChat } = useChat();
  const [sets, setSets] = useState<SetChoice>(null);       // null = every set (General always among them)
  const name = info(active)?.native ?? active;
  useEffect(() => { setSets(null); }, [active]);

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
        <Conversation messages={messages} sending={sending} languageName={name} onRetry={(id) => retry(id, active, setIdsToSend(sets))} />
        <Composer language={active} sets={sets} onSets={setSets} sending={sending} onSend={(text) => send(text, active, setIdsToSend(sets))} />
      </Card>
      <div className="mt-4"><Notice>{t("chat.notice")}</Notice></div>
    </div>
  );
}
