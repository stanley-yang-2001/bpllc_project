import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Pencil } from "lucide-react";
import { useState } from "react";
import { wordsKey } from "../api/keys";
import { api, type Word } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n/I18nProvider";
import { ErrorText, inputCls } from "../components/ui";

/** One word's meaning: click to edit, Enter or leaving the box saves, Escape cancels. */
export function MeaningCell({ word, language }: { word: Word; language: string }) {
  const qc = useQueryClient();
  const { user } = useAuth();
  const { t, err } = useI18n();
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(word.meaning ?? "");
  const save = useMutation({
    mutationFn: (meaning: string | null) => api.editWord(word.id, { meaning }),
    onSuccess: () => { setEditing(false); void qc.invalidateQueries({ queryKey: wordsKey(user!.id, language) }); },
  });
  const commit = () => {
    const next = text.trim() || null;
    if (next === (word.meaning ?? null)) return setEditing(false);
    save.mutate(next);
  };
  if (!editing)
    return (
      <button
        className="group inline-flex items-center gap-1.5 rounded text-left text-slate-700 hover:text-slate-900"
        onClick={() => { setText(word.meaning ?? ""); setEditing(true); }}
        aria-label={t("vocab.editMeaning", { word: word.word })}
      >
        {word.meaning ?? <span className="text-slate-600">{t("vocab.addMeaning")}</span>}
        <Pencil aria-hidden className="size-3.5 text-slate-500 opacity-0 transition group-hover:opacity-100 group-focus-visible:opacity-100" />
      </button>
    );
  return (
    <div>
      <input
        autoFocus
        aria-label={t("vocab.meaningOf", { word: word.word })}
        className={`${inputCls} py-1.5`}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => { if (e.key === "Enter") commit(); if (e.key === "Escape") setEditing(false); }}
      />
      <ErrorText>{save.error ? err(save.error) : undefined}</ErrorText>
    </div>
  );
}
