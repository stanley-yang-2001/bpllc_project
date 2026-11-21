import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type GlossResult } from "../api/client";
import { wordsKey } from "../api/keys";
import { useAuth } from "../auth/AuthContext";
import { Button, ErrorText } from "../components/ui";
import { useToast } from "../components/Toast";
import { useI18n } from "../i18n/I18nProvider";
import { usePreferences } from "../prefs/PreferencesProvider";
import { SpeakButton } from "../speech/SpeakButton";
import { learnable } from "./segments";

/** The card for the word that was tapped in a story: what it means and how it sounds, and for a word that is not in the learner's list a way to add it.
 * Which word it shows is found from the place in the text (not from an id), so a word added from here shows its meaning as soon as the text is read again. */
export function WordCard({ text, language, at, gloss, onClose }: {
  text: string; language: string; at: { start: number; end: number }; gloss: GlossResult; onClose: () => void;
}) {
  const { t, err } = useI18n();
  const { user } = useAuth();
  const { prefs } = usePreferences();
  const qc = useQueryClient();
  const toast = useToast();
  const [withMeaning, setWithMeaning] = useState(true);
  const span = gloss.spans.find((s) => s.start === at.start);
  const known = span ? gloss.words.find((w) => w.id === span.word_id) : undefined;
  const written = text.slice(at.start, at.end);
  const shown = known ? known.word : written;
  const refresh = () => qc.invalidateQueries({ queryKey: wordsKey(user!.id, language) });
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const add = useMutation({
    // not optimistic: the server normalises the word and may refuse it as a duplicate
    mutationFn: async () => {
      const w = await api.addWord({ language, word: learnable(text, at.start, at.end, language) });
      if (withMeaning) await api.defineWords({ ids: [w.id], language, meaning_mode: prefs.meaning_mode }).catch(() => undefined);      // the word is kept even if the tutor can't answer now
      return w;
    },
    onSuccess: (w) => { toast(t("vocab.added", { word: w.word })); void refresh(); },
  });
  const define = useMutation({
    mutationFn: () => api.defineWords({ ids: [known!.id], language, meaning_mode: prefs.meaning_mode }),
    onSuccess: () => void refresh(),
  });
  const failure = add.error ?? define.error;

  return (
    <div role="region" aria-label={t("reader.card")} aria-live="polite"
      className="fixed inset-x-3 bottom-3 z-40 mx-auto max-w-xl rounded-xl border border-slate-200 bg-surface p-4 shadow-lg">
      <div className="flex items-start justify-between gap-3">
        <p lang={language} className="text-lg font-semibold text-slate-900">{shown}</p>
        <Button type="button" variant="ghost" className="-mr-2 -mt-1 px-2" aria-label={t("common.close")} onClick={onClose} icon={<X aria-hidden className="size-4" />} />
      </div>
      {known ? (
        known.meaning ? <p className="mt-1 text-base text-slate-800">{known.meaning}</p> : (
          <div className="mt-1 space-y-2">
            <p className="text-sm text-slate-600">{t("reader.noMeaning")}</p>
            <Button type="button" variant="secondary" loading={define.isPending} onClick={() => define.mutate()}>{t("vocab.defineAdd")}</Button>
          </div>
        )
      ) : <p className="mt-1 text-sm text-slate-600">{t("reader.notInList", { word: written })}</p>}
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
        <SpeakButton text={shown} language={language} label={t("speech.listen")} />
        {!known && (
          <>
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={withMeaning} onChange={(e) => setWithMeaning(e.target.checked)} />
              {t("vocab.defineAdd")}
            </label>
            <Button type="button" loading={add.isPending} onClick={() => add.mutate()} icon={<Plus aria-hidden className="size-4" />}>{t("vocab.addWord")}</Button>
          </>
        )}
      </div>
      {failure && <ErrorText>{err(failure)}</ErrorText>}
    </div>
  );
}
