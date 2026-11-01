import { Search, Sparkles, Tags, Type, Upload } from "lucide-react";
import { useRef } from "react";
import { Button, inputCls } from "../components/ui";
import { useI18n } from "../i18n/I18nProvider";
import { MeaningLanguage } from "./MeaningLanguage";

const tool = "w-full whitespace-nowrap sm:w-56";       // every button here is the same size, so the rows line up

type Props = {
  search: string; onSearch: (value: string) => void;
  showReading: boolean; readingLoading: boolean; onToggleReading: () => void;
  defining: boolean; onDefine: () => void;
  labelling: boolean; onLabel: () => void;
  uploading: boolean; onCsv: (file: File) => void;
};

/** Above the word table. First row: search, then what to show and what to bring in. Second row: the tutor's tools (the language the
 * meanings are written in, then the two buttons that fill in what is missing). All buttons share one size and height. */
export function Toolbar(p: Props) {
  const { t } = useI18n();
  const fileRef = useRef<HTMLInputElement>(null);
  return (
    <div className="space-y-3 border-b border-slate-200 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-52 max-w-sm flex-1">
          <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-500" />
          <input aria-label={t("vocab.searchAria")} placeholder={t("vocab.searchPlaceholder")} value={p.search} onChange={(e) => p.onSearch(e.target.value)} className={`${inputCls} pl-9`} />
        </div>
        <div className="flex w-full flex-col gap-2 sm:ml-auto sm:w-auto sm:flex-row">
          <Button variant="secondary" className={tool} aria-pressed={p.showReading} loading={p.readingLoading} icon={<Type aria-hidden className="size-4" />} onClick={p.onToggleReading}>
            {p.showReading ? t("reading.hide") : t("reading.show")}
          </Button>
          <input ref={fileRef} type="file" accept=".csv,text/csv" hidden aria-label={t("vocab.csvFile")} onChange={(e) => { const f = e.target.files?.[0]; if (f) p.onCsv(f); e.target.value = ""; }} />
          <Button variant="secondary" className={tool} loading={p.uploading} icon={<Upload aria-hidden className="size-4" />} onClick={() => fileRef.current?.click()}>{t("vocab.uploadCsv")}</Button>
        </div>
      </div>
      <div className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-slate-50/60 p-3 dark:bg-slate-100/40 sm:flex-row sm:flex-wrap sm:items-center sm:gap-3">
        <MeaningLanguage />
        <div className="flex flex-col gap-2 sm:ml-auto sm:flex-row">
          <Button variant="secondary" className={tool} loading={p.defining} icon={<Sparkles aria-hidden className="size-4" />} onClick={p.onDefine}>{t("vocab.defineMissing")}</Button>
          <Button variant="secondary" className={tool} loading={p.labelling} icon={<Tags aria-hidden className="size-4" />} onClick={p.onLabel}>{t("vocab.labelMissing")}</Button>
        </div>
      </div>
    </div>
  );
}
