import { BookmarkPlus } from "lucide-react";
import type { ToolCall } from "../api/client";
import { Button, ErrorText } from "../components/ui";
import { useI18n } from "../i18n/I18nProvider";
import { useSaveStory } from "../library/useSaveStory";

/** Offers to keep a story the tutor wrote. The API makes the quality report when it saves; the chat itself is not stored. */
export function SaveStory({ call, language }: { call: ToolCall; language: string }) {
  const { t, err } = useI18n();
  const save = useSaveStory();
  return (
    <div className="mt-2">
      <Button variant="secondary" onClick={() => save.mutate({ language, body: call.output, story_type: null, topic: null })} disabled={save.isSuccess} loading={save.isPending} icon={<BookmarkPlus aria-hidden className="size-4" />}>
        {save.isSuccess ? t("chat.saved") : t("chat.saveStory")}
      </Button>
      {save.error && <ErrorText>{err(save.error, "common.saveFailed")}</ErrorText>}
    </div>
  );
}
