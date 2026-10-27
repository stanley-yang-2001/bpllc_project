import { Languages, Trash2 } from "lucide-react";
import { useState } from "react";
import type { WordSet } from "../api/client";
import { useConfirm } from "../components/Confirm";
import { useI18n } from "../i18n/I18nProvider";
import { Button, inputCls } from "../components/ui";

type Props = {
  count: number;
  sets: WordSet[];
  moving: boolean;
  translating: boolean;
  onMove: (to: number | null) => void;
  onToggleTranslate: () => void;
  onClear: () => void;
  onDelete: () => void;
};

/** What can be done to the ticked words: move to a set, translate, clear the ticks, delete (after a confirmation). */
export function BulkBar({ count, sets, moving, translating, onMove, onToggleTranslate, onClear, onDelete }: Props) {
  const { t } = useI18n();
  const confirm = useConfirm();
  const [moveTo, setMoveTo] = useState("");
  return (
    <div className="flex items-center justify-between gap-3 border-b border-brand-200 bg-brand-50 px-4 py-2 text-sm text-brand-900 dark:border-brand-800 dark:bg-brand-900/40 dark:text-brand-100">
      <span>{t("vocab.selected", { count })}</span>
      <div className="flex flex-wrap items-center gap-2">
        <select aria-label={t("sets.moveAria")} className={`${inputCls} w-auto`} value={moveTo} disabled={moving}
          onChange={(e) => { const v = e.target.value; setMoveTo(v); if (v !== "") onMove(v === "general" ? null : Number(v)); }}>
          <option value="">{t("sets.moveTo")}</option>
          <option value="general">{t("sets.general")}</option>
          {sets.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
        </select>
        <Button variant="secondary" aria-pressed={translating} icon={<Languages aria-hidden className="size-4" />} onClick={onToggleTranslate}>{t("translate.selectWords")}</Button>
        <Button variant="ghost" onClick={onClear}>{t("common.clear")}</Button>
        <Button variant="danger" icon={<Trash2 aria-hidden className="size-4" />}
          onClick={async () => {
            const ok = await confirm({
              title: count === 1 ? t("vocab.deleteOne.title") : t("vocab.deleteMany.title", { count }),
              body: t("vocab.deleteBody"),
              confirmLabel: count === 1 ? t("vocab.deleteOne.confirm") : t("vocab.deleteMany.confirm", { count }),
            });
            if (ok) onDelete();
          }}>
          {t("vocab.deleteSelected", { count })}
        </Button>
      </div>
    </div>
  );
}
