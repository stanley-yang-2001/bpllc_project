import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { api } from "../api/client";
import { progressKey } from "../api/keys";
import { useAuth } from "../auth/AuthContext";

/** Remember each answer as it is given, so a round left half-way still counts. A failure never stops the round: it is shown
 * once on the result screen (`failed`). A blank with no word id behind it (an old cached item) is simply not recorded. */
export function useAnswerRecorder(language: string) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [failed, setFailed] = useState(false);
  const record = useCallback((wordId: number | null | undefined, correct: boolean) => {
    if (!wordId) return;
    api.recordAnswers([{ word_id: wordId, correct }])
      .then(() => qc.invalidateQueries({ queryKey: progressKey(user!.id, language) }))
      .catch(() => setFailed(true));
  }, [qc, user, language]);
  return { record, failed };
}
