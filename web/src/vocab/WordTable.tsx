import type { Word } from "../api/client";
import { SpeakButton } from "../speech/SpeakButton";
import { useI18n } from "../i18n/I18nProvider";
import { MeaningCell } from "./MeaningCell";

type Props = {
  words: Word[];
  language: string;
  selected: Set<number>;
  onToggle: (id: number) => void;
  onToggleAll: () => void;
  readings: Map<string, string | null>;       // word -> reading, shown under the word when it has one
  showReadings: boolean;
  setNames: Map<number, string> | null;  // null = no sets yet, so no Set column
};

/** The table of words with tick boxes, a speak button, an optional reading, an editable meaning and (when there are sets) the set. */
export function WordTable({ words, language, selected, onToggle, onToggleAll, readings, showReadings, setNames }: Props) {
  const { t } = useI18n();
  const allOnPage = words.length > 0 && words.every((w) => selected.has(w.id));
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <th className="w-12 py-3 pl-4">
              <input type="checkbox" className="size-4 rounded accent-brand-600" aria-label={t("vocab.selectAll")} checked={allOnPage} onChange={onToggleAll} />
            </th>
            <th className="py-3 pr-4">{t("vocab.colWord")}</th>
            <th className="py-3 pr-4">{t("vocab.colMeaning")}</th>
            {setNames && <th className="py-3 pr-4">{t("sets.column")}</th>}
          </tr>
        </thead>
        <tbody>
          {words.map((w) => (
            <tr key={w.id} className={`border-b border-slate-100 last:border-0 transition-colors hover:bg-slate-100/70 ${selected.has(w.id) ? "bg-brand-50/60 dark:bg-brand-900/30" : ""}`}>
              <td className="py-2.5 pl-4">
                <input type="checkbox" className="size-4 rounded accent-brand-600" aria-label={t("vocab.select", { word: w.word })} checked={selected.has(w.id)} onChange={() => onToggle(w.id)} />
              </td>
              <td className="py-2.5 pr-4 font-medium text-slate-900"><span lang={language}>{w.word}</span> <SpeakButton text={w.word} language={language} />{showReadings && readings.get(w.word) && <span className="block text-xs font-normal text-slate-600">{readings.get(w.word)}</span>}</td>
              <td className="py-2.5 pr-4"><MeaningCell word={w} language={language} /></td>
              {setNames && <td className="py-2.5 pr-4 text-slate-600">{w.set_id ? setNames.get(w.set_id) ?? "" : t("sets.general")}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
