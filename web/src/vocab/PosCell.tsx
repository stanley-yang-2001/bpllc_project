import { useMutation, useQueryClient } from "@tanstack/react-query";
import { wordsKey } from "../api/keys";
import { api, type Word } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n/I18nProvider";
import { ErrorText, inputCls } from "../components/ui";
import { posKeyOf, usePosCategories } from "./usePos";

/** One word's part of speech: a list of this language's own categories; choosing one saves it, "no label" clears it. */
export function PosCell({ word, language }: { word: Word; language: string }) {
  const qc = useQueryClient();
  const { user } = useAuth();
  const { t, err } = useI18n();
  const cats = usePosCategories(language);
  const save = useMutation({
    mutationFn: (pos: string | null) => api.editWord(word.id, { pos }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: wordsKey(user!.id, language) }),
  });
  const label = (code: string) => { const k = posKeyOf(code); return k ? t(k) : code; };
  const codes = cats.data?.items ?? [];
  const options = word.pos && !codes.includes(word.pos) ? [word.pos, ...codes] : codes;
  return (
    <div>
      <select aria-label={t("vocab.posOf", { word: word.word })} className={`${inputCls} w-auto min-w-32 py-1 text-xs`} value={word.pos ?? ""}
        disabled={save.isPending || cats.isPending} onChange={(e) => save.mutate(e.target.value || null)}>
        <option value="">{t("vocab.posNone")}</option>
        {options.map((c) => <option key={c} value={c}>{label(c)}</option>)}
      </select>
      <ErrorText>{save.error ? err(save.error) : undefined}</ErrorText>
    </div>
  );
}
