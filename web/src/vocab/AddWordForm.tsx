import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { wordsKey } from "../api/keys";
import { api, type SetFilter, type WordSet } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { useI18n } from "../i18n/I18nProvider";
import { Button, Card, ErrorText, inputCls } from "../components/ui";
import { usePreferences } from "../prefs/PreferencesProvider";
import { MeaningLanguage } from "./MeaningLanguage";

type Props = { language: string; languageName: string; sets: WordSet[]; filter: SetFilter; onChanged: () => void };

/** The "add a word" card. A new word goes into the set the learner picked, else the set they are looking at, else General. */
export function AddWordForm({ language, languageName, sets, filter, onChanged }: Props) {
  const qc = useQueryClient();
  const toast = useToast();
  const { user } = useAuth();
  const { t, err } = useI18n();
  const { prefs } = usePreferences();
  const [wantMeaning, setWantMeaning] = useState(false);
  const [picked, setPicked] = useState("");
  const form = useForm<{ word: string; meaning: string }>({ defaultValues: { word: "", meaning: "" } });
  useEffect(() => setPicked(""), [language]);

  const add = useMutation({
    // not optimistic: the server normalises the word and may reject it as a duplicate
    mutationFn: async (v: { word: string; meaning: string }) => {
      const target = picked !== "" ? Number(picked) : typeof filter === "number" ? filter : null;
      const w = await api.addWord({ language, word: v.word, meaning: v.meaning || undefined, ...(target !== null ? { set_id: target } : {}) });
      if (wantMeaning && !v.meaning) await api.defineWords({ ids: [w.id], language, meaning_mode: prefs.meaning_mode }).catch(() => undefined);   // the word is kept even if the tutor can't answer now
      return w;
    },
    onSuccess: (w) => {
      form.reset();
      toast(t("vocab.added", { word: w.word }));
      onChanged();
      void qc.invalidateQueries({ queryKey: wordsKey(user!.id, language) });
      void qc.invalidateQueries({ queryKey: ["me"] });
    },
  });

  return (
    <Card className="mb-6">
      <form onSubmit={form.handleSubmit((v) => add.mutate(v))} className="flex flex-wrap items-start gap-3" aria-label={t("vocab.addForm")}>
        <div className="min-w-44 flex-1">
          <input aria-label={t("vocab.word")} placeholder={t("vocab.wordPlaceholder", { language: languageName })} className={inputCls} data-word-input {...form.register("word", { required: true })} />
        </div>
        <div className="min-w-44 flex-1">
          <input aria-label={t("vocab.meaningOptional")} placeholder={t("vocab.meaningOptional")} className={inputCls} {...form.register("meaning")} />
        </div>
        {sets.length > 0 && (
          <div className="w-44">
            <select aria-label={t("sets.column")} className={inputCls} value={picked !== "" ? picked : typeof filter === "number" ? String(filter) : ""} onChange={(e) => setPicked(e.target.value)}>
              <option value="">{t("sets.general")}</option>
              {sets.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
            </select>
          </div>
        )}
        <Button type="submit" loading={add.isPending} icon={<Plus aria-hidden className="size-4" />}>{t("vocab.addWord")}</Button>
        <div className="flex w-full flex-wrap items-center gap-x-6 gap-y-2">
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" className="size-4 rounded accent-brand-600" checked={wantMeaning} onChange={(e) => setWantMeaning(e.target.checked)} />
            {t("vocab.defineAdd")}
          </label>
          {wantMeaning && <MeaningLanguage />}
        </div>
      </form>
      <ErrorText>{add.error ? err(add.error) : undefined}</ErrorText>
      <p className="mt-3 text-xs text-slate-500">{t("vocab.storedHint")} {t("vocab.defineHint")}</p>
    </Card>
  );
}
