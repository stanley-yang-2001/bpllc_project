import { useMutation, useQueryClient } from "@tanstack/react-query";
import { wordsKey } from "../api/keys";
import { api, type WordPage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { useI18n } from "../i18n/I18nProvider";

/** Deleting and moving the selected words. `onDone` clears the selection; `onChanged` refreshes the set counts. */
export function useBulkActions(language: string, onDone: () => void, onChanged: () => void) {
  const qc = useQueryClient();
  const toast = useToast();
  const { user } = useAuth();
  const { tc } = useI18n();
  const key = wordsKey(user!.id, language);

  const remove = useMutation({
    mutationFn: (ids: number[]) => api.deleteWords(ids),
    onMutate: async (ids) => {            // optimistic: deleting can't be rejected by normalisation
      await qc.cancelQueries({ queryKey: key });
      const snapshot = qc.getQueriesData<WordPage>({ queryKey: key });
      qc.setQueriesData<WordPage>({ queryKey: key }, (p) =>
        p ? { ...p, items: p.items.filter((w) => !ids.includes(w.id)), total: Math.max(0, p.total - ids.length) } : p);
      onDone();
      return { snapshot };
    },
    onSuccess: (r) => toast(tc("vocab.deleted", r.deleted)),
    onError: (_e, _ids, ctx) => ctx?.snapshot.forEach(([k, data]) => qc.setQueryData(k, data)),
    onSettled: () => { onChanged(); void qc.invalidateQueries({ queryKey: key }); },
  });

  const move = useMutation({
    mutationFn: (v: { ids: number[]; to: number | null }) => api.moveWords(v.ids, v.to),
    onSuccess: (r) => { toast(tc("sets.moved", r.moved)); onDone(); onChanged(); void qc.invalidateQueries({ queryKey: key }); },
  });

  return { remove, move };
}
