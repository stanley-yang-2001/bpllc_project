import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, type GeneratedStory } from "../api/client";
import { storiesKey } from "../api/keys";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n/I18nProvider";
import { useToast } from "../components/Toast";

/** Making a story and saving it. A story belongs to one language, so changing the language clears it. */
export function useStoryGeneration(language: string, onLanguageChange: () => void) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const { t } = useI18n();
  const [story, setStory] = useState<GeneratedStory | null>(null);
  const [savedId, setSavedId] = useState<number | null>(null);
  const generate = useMutation({ mutationFn: api.generateStory, onSuccess: (s) => { setStory(s); setSavedId(null); } });
  const save = useMutation({
    mutationFn: api.saveStory,
    onSuccess: (s) => {
      setSavedId(s.id);
      toast(t("common.savedToLibrary"));
      if (user) void qc.invalidateQueries({ queryKey: storiesKey(user.id) });
    },
  });
  useEffect(() => { onLanguageChange(); setStory(null); setSavedId(null); generate.reset(); save.reset(); }, [language]);
  return { story, savedId, saved: savedId !== null, generate, save };
}
export type StoryGeneration = ReturnType<typeof useStoryGeneration>;
