import { ChevronLeft, ChevronRight } from "lucide-react";
import { useI18n } from "../i18n/I18nProvider";
import { Badge, Button } from "../components/ui";

type Props = { offset: number; limit: number; total: number; onOffset: (n: number) => void };

export function Pager({ offset, limit, total, onOffset }: Props) {
  const { t } = useI18n();
  if (total <= limit) return null;
  return (
    <div className="flex items-center justify-between border-t border-slate-200 p-3 text-sm text-slate-600">
      <Button variant="ghost" disabled={offset === 0} onClick={() => onOffset(Math.max(0, offset - limit))} icon={<ChevronLeft aria-hidden className="size-4" />}>{t("common.previous")}</Button>
      <Badge>{t("common.range", { from: offset + 1, to: Math.min(offset + limit, total), total })}</Badge>
      <Button variant="ghost" disabled={offset + limit >= total} onClick={() => onOffset(offset + limit)}>{t("common.next")}<ChevronRight aria-hidden className="size-4" /></Button>
    </div>
  );
}
