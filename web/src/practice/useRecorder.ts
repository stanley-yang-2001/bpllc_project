import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { Answer } from "../api/types";
import { progressKey, rewardsKey } from "../api/keys";
import { useAuth } from "../auth/AuthContext";

/** Remember each answer as it is given, so a round left half-way still counts. A failure never stops the round: it is shown
 * once on the result screen (`failed`). A blank with no word id behind it (an old cached item) is simply not recorded. */
export function useAnswerRecorder(language: string) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [failed, setFailed] = useState(false);
  const record = useCallback((wordId: number | null | undefined, correct: boolean, extra: Pick<Answer, "think_ms" | "mode" | "direction"> = {}) => {
    if (!wordId) return;
    api.recordAnswers([{ word_id: wordId, correct, ...extra }])
      .then(() => Promise.all([qc.invalidateQueries({ queryKey: progressKey(user!.id, language) }), qc.invalidateQueries({ queryKey: rewardsKey(user!.id, language) })]))
      .catch(() => setFailed(true));
  }, [qc, user, language]);
  return { record, failed };
}

/** How long the current question has been on screen, in milliseconds: starts again whenever `key` changes (the next question) and only
 * once `ready` (the questions have loaded). Used for "how long did you take"; the number is sent with the answer. */
export function useThinkTimer(key: unknown, ready = true) {
  const startedAt = useRef(performance.now());
  useEffect(() => { startedAt.current = performance.now(); }, [key, ready]);
  return useCallback(() => Math.round(performance.now() - startedAt.current), []);
}
