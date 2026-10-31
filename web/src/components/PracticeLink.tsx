import { GraduationCap } from "lucide-react";
import { Link } from "react-router-dom";
import { useI18n } from "../i18n/I18nProvider";

/** "Practise" for one saved story: opens Practice on that story. Looks like a secondary button. */
export function PracticeLink({ storyId }: { storyId: number }) {
  const { t } = useI18n();
  return (
    <Link to={`/practice?story=${storyId}`} className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-surface px-3.5 py-2 text-sm font-medium text-slate-700 shadow-xs hover:bg-slate-100/70">
      <GraduationCap aria-hidden className="size-4" />{t("studio.practice")}
    </Link>
  );
}
