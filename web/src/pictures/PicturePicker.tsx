import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ImagePlus, Trash2 } from "lucide-react";
import { useState } from "react";
import { api } from "../api/client";
import { wordsKey } from "../api/keys";
import type { Picture } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Modal } from "../components/Modal";
import { useToast } from "../components/Toast";
import { Button, ErrorText, inputCls } from "../components/ui";
import { useI18n } from "../i18n/I18nProvider";
import EMOJI from "./emojis.json";
import { PictureThumb } from "./PictureThumb";
import { PhotoUnreadable, shrinkPhoto } from "./shrink";

const GROUPS = ["food", "nature", "people", "places", "things", "signs"] as const;

/** The word a picture is for: only what the dialog needs, so it works for a row of the word list and for the reader's card alike. */
export type PictureTarget = { id: number; word: string; picture?: Picture | null };

/** The dialog to give a word a picture: one emoji (from the grid, or any emoji typed or pasted) or the learner's own photo, and a way to take
 * the picture off. Saving replaces whatever picture the word had, refreshes the words (and so the list, the cards and the reader) and closes. */
export function PicturePicker({ word, language, onClose }: { word: PictureTarget; language: string; onClose: () => void }) {
  const { t, err } = useI18n();
  const { user } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const [typed, setTyped] = useState("");
  const done = (message: string) => {
    void qc.invalidateQueries({ queryKey: wordsKey(user!.id, language) });
    toast(message);
    onClose();
  };
  const emoji = useMutation({ mutationFn: (e: string) => api.setEmoji(word.id, e), onSuccess: () => done(t("pictures.saved")) });
  const photo = useMutation({
    mutationFn: async (file: File) => api.setPhoto(word.id, await shrinkPhoto(file)),
    onSuccess: () => done(t("pictures.saved")),
  });
  const remove = useMutation({ mutationFn: () => api.removePicture(word.id), onSuccess: () => done(t("pictures.removed")) });
  const busy = emoji.isPending || photo.isPending || remove.isPending;
  const failure = emoji.error ?? photo.error ?? remove.error;

  return (
    <Modal open onClose={onClose} title={t("pictures.title", { word: word.word })}>
      <div className="space-y-5">
        {word.picture && (
          <div className="flex items-center gap-4">
            <PictureThumb picture={word.picture} size="md" />
            <Button type="button" variant="secondary" disabled={busy} loading={remove.isPending} onClick={() => remove.mutate()} icon={<Trash2 aria-hidden className="size-4" />}>
              {t("pictures.remove")}
            </Button>
          </div>
        )}

        <section aria-label={t("pictures.emoji")}>
          <h3 className="mb-2 text-sm font-semibold text-slate-800">{t("pictures.emoji")}</h3>
          <div className="max-h-56 space-y-3 overflow-y-auto pr-1">
            {GROUPS.map((g, i) => (
              <div key={g} role="group" aria-label={t(`pictures.group.${g}`)}>
                <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">{t(`pictures.group.${g}`)}</p>
                <div className="flex flex-wrap gap-0.5">
                  {EMOJI[g].map((e, j) => (
                    <button key={e} type="button" disabled={busy} onClick={() => emoji.mutate(e)} data-autofocus={i === 0 && j === 0 ? "" : undefined}
                      className="size-9 rounded-lg text-xl leading-none transition hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-brand-500 disabled:opacity-50">
                      {e}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); if (typed.trim()) emoji.mutate(typed.trim()); }}>
            <input className={`${inputCls} w-full`} aria-label={t("pictures.emojiAny")} placeholder={t("pictures.emojiAny")} value={typed} maxLength={16}
              onChange={(e) => setTyped(e.target.value)} />
            <Button type="submit" variant="secondary" disabled={busy || !typed.trim()} className="shrink-0">{t("pictures.emojiUse")}</Button>
          </form>
        </section>

        <section>
          <h3 className="mb-2 text-sm font-semibold text-slate-800">{t("pictures.photo")}</h3>
          <label className={`inline-flex cursor-pointer items-center gap-2 rounded-lg border border-slate-300 bg-surface px-3.5 py-2 text-sm font-medium text-slate-700 shadow-xs hover:bg-slate-100/70 focus-within:ring-2 focus-within:ring-brand-500/40 ${busy ? "pointer-events-none opacity-50" : ""}`}>
            <ImagePlus aria-hidden className="size-4" />
            {t("pictures.choosePhoto")}
            <input type="file" accept="image/*" className="sr-only" disabled={busy}
              onChange={(e) => { const file = e.target.files?.[0]; e.target.value = ""; if (file) photo.mutate(file); }} />
          </label>
          <p className="mt-2 text-xs text-slate-600">{t("pictures.photoNote")}</p>
        </section>

        {failure && <ErrorText>{failure instanceof PhotoUnreadable ? t("pictures.cannotRead") : err(failure)}</ErrorText>}
      </div>
    </Modal>
  );
}
