import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { wordsKey } from "../api/keys";
import { useAuth } from "../auth/AuthContext";

/** The learner's own words in a text. Cached under the words, so adding, editing or deleting a word refreshes it. When it fails the text just stays plain. */
export function useGloss(text: string, language: string) {
  const { user } = useAuth();
  return useQuery({
    queryKey: wordsKey(user!.id, language, "gloss", text),
    queryFn: () => api.gloss({ language, text }),
    enabled: text.trim() !== "",
    staleTime: 5 * 60_000,
    retry: false,
  });
}
