import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, type GeneratedStory } from "../api/client";
import { useSaveStory } from "../library/useSaveStory";

/** Making a story and saving it. A story belongs to one language, so changing the language clears it. */
export function useStoryGeneration(language: string, onLanguageChange: () => void) {
  const [story, setStory] = useState<GeneratedStory | null>(null);
  const [savedId, setSavedId] = useState<number | null>(null);
  const generate = useMutation({ mutationFn: api.generateStory, onSuccess: (s) => { setStory(s); setSavedId(null); } });
  const save = useSaveStory((saved) => setSavedId(saved.id));
  useEffect(() => { onLanguageChange(); setStory(null); setSavedId(null); generate.reset(); save.reset(); }, [language]);
  return { story, savedId, saved: savedId !== null, generate, save };
}
export type StoryGeneration = ReturnType<typeof useStoryGeneration>;
