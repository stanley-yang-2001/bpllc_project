import { useQuery } from "@tanstack/react-query";
import { GraduationCap } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { progressKey } from "../api/keys";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n/I18nProvider";
import { Badge, Card, PageHeader } from "../components/ui";
import { ModeSession, ModeTileFor, MODE_ORDER, type Launch, type PracticeContext } from "../practice/modes";
import { ProgressCard } from "../practice/ProgressCard";
import { pickedToFilter, SetPicker } from "../practice/SetPicker";
import { StudyStats } from "../practice/StudyStats";

export default function Practice() {
  const { active, info } = useActiveLanguage();
  const { user } = useAuth();
  const { t } = useI18n();
  const [params, setParams] = useSearchParams();
  const name = info(active)?.native ?? active;
  const storyParam = Number(params.get("story"));
  const storyId = Number.isInteger(storyParam) && storyParam > 0 ? storyParam : null;
  const [launched, setLaunched] = useState<Launch | null>(null);
  const [picked, setPicked] = useState<string[]>([]);          // the sets chosen ("general" or a set id); none = every word
  const [dueOnly, setDueOnly] = useState(false);                 // only words that are due for review (then never-practised ones)
  const filter = pickedToFilter(picked);
  const progress = useQuery({ queryKey: [...progressKey(user!.id, active), String(filter)], queryFn: () => api.practiceProgress(active, filter) });
  useEffect(() => { setLaunched(null); setPicked([]); setDueOnly(false); }, [active]);

  // a story in the address (?story=12, from the Library) opens the blanks exercise; everything else is chosen on this page
  const launch: Launch | null = launched ?? (storyId !== null ? { mode: "cloze", storyId } : null);
  const start = (l: Launch) => { if (l.mode === "cloze") setParams({ story: String(l.storyId) }); else setLaunched(l); };
  const back = () => { setLaunched(null); setParams({}); };
  const ctx: PracticeContext = { language: active, name, set: filter, dueOnly, progress: progress.data };
  return (
    <div>
      <PageHeader title={t("nav.practice")} description={t("practice.description")} actions={<Badge tone="brand"><span lang={active}>{name}</span></Badge>} />
      {launch ? (
        <Card><ModeSession launch={launch} ctx={ctx} onDone={back} start={start} /></Card>
      ) : (
        <>
        <SetPicker language={active} picked={picked} onChange={setPicked} />
        <ProgressCard language={active} set={filter} onReview={() => start({ mode: "cards", scope: "due", ids: [] })} />
        <StudyStats language={active} set={filter} onPractise={(ids) => start({ mode: "cards", scope: "ids", ids })} />
        <label className="mb-4 flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={dueOnly} onChange={(e) => setDueOnly(e.target.checked)} />{t("practice.dueOnly")}
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          {MODE_ORDER.map((id) => <ModeTileFor key={id} id={id} ctx={ctx} start={start} />)}
        </div>
        <p className="mt-4 flex items-center gap-2 text-xs text-slate-600"><GraduationCap aria-hidden className="size-4" />{t("practice.footer")}</p>
        </>
      )}
    </div>
  );
}
