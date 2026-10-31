import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BookmarkPlus } from "lucide-react";
import { api, type ToolCall } from "../api/client";
import { storiesKey } from "../api/keys";
import { useAuth } from "../auth/AuthContext";
import { Button, ErrorText } from "../components/ui";
import { useToast } from "../components/Toast";
import { useI18n } from "../i18n/I18nProvider";

/** Offers to keep a story the tutor wrote. The API makes the quality report when it saves; the chat itself is not stored. */
export function SaveStory({ call, language }: { call: ToolCall; language: string }) {
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
