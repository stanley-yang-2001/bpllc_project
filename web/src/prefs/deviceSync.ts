import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import type { User } from "../api/client";
import { COPY_KEY, readCopy, wipeCopy, writeCopy, type Prefs } from "./deviceCopy";

/** The device copy follows the account; nobody signed in means no copy at all. */
export function useWriteDeviceCopy(loading: boolean, userId: number | null, prefs: Prefs) {
  useEffect(() => {
    if (loading) return;
    if (userId === null) { wipeCopy(); return; }
    writeCopy(userId, {
      theme: prefs.theme, custom_colors: prefs.custom_colors,
      active_language: prefs.active_language, ui_follows_study_language: prefs.ui_follows_study_language,
    });
  }, [loading, userId, prefs]);
}

/** Another tab changed the copy for this same person: follow it. */
export function useFollowOtherTabs(userId: number | null) {
  const qc = useQueryClient();
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key !== COPY_KEY || userId === null) return;
      const copy = readCopy();
      if (!copy || copy.userId !== userId) return;
      qc.setQueryData<User | null>(["me"], (me) => me && me.id === userId ? {
        ...me,
        preferences: {
          chat_in_study_language: me.preferences?.chat_in_study_language ?? false,
          meaning_mode: me.preferences?.meaning_mode ?? "native",
          theme: copy.theme, custom_colors: copy.custom_colors,
          active_language: copy.active_language, ui_follows_study_language: copy.ui_follows_study_language,
        },
      } : me);
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [qc, userId]);
}
