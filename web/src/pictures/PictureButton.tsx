import { ImagePlus } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useI18n } from "../i18n/I18nProvider";
import { PicturePicker, type PictureTarget } from "./PicturePicker";
import { PictureThumb } from "./PictureThumb";

/** A word's picture as a button that opens the dialog to change it; a word with none shows a faint square with a plus. */
export function PictureButton({ word, language }: { word: PictureTarget; language: string }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const button = useRef<HTMLButtonElement>(null);
  const was = useRef(false);
  useEffect(() => {                                  // the dialog is gone: hand focus back to the button that opened it
    if (was.current && !open) button.current?.focus();
    was.current = open;
  }, [open]);
  return (
    <>
      <button ref={button} type="button" onClick={() => setOpen(true)} aria-label={t(word.picture ? "pictures.change" : "pictures.add", { word: word.word })}
        className="inline-flex rounded-lg focus-visible:outline-2 focus-visible:outline-brand-500">
        {word.picture ? (
          <PictureThumb picture={word.picture} />
        ) : (
          <span className="inline-flex size-9 items-center justify-center rounded-lg border border-dashed border-slate-300 text-slate-500 transition hover:border-brand-500 hover:text-brand-600">
            <ImagePlus aria-hidden className="size-4" />
          </span>
        )}
      </button>
      {open && <PicturePicker word={word} language={language} onClose={() => setOpen(false)} />}
    </>
  );
}
