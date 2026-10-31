import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { storiesKey } from "../api/keys";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { useI18n } from "../i18n/I18nProvider";

/** Keeping a story: saves it, says so, and refreshes the Library's lists. Studio and Chat both save this way. */
export function useSaveStory(onSaved?: (saved: { id: number }) => void) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const { t } = useI18n();
  return useMutation({
    mutationFn: api.saveStory,
    onSuccess: (saved) => {
      toast(t("common.savedToLibrary"));
      if (user) void qc.invalidateQueries({ queryKey: storiesKey(user.id) });
      onSaved?.(saved);
    },
  });
}
