import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { wordsKey } from "../api/keys";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { useAuth } from "../auth/AuthContext";
import { Card } from "../components/ui";
import { useI18n } from "../i18n/I18nProvider";
import { PictureButton } from "../pictures/PictureButton";
import { SpeakButton } from "../speech/SpeakButton";

/** One of the learner's own words for today, picked from the ones they have met least (the server keeps it the same all day), with its picture, its meaning and
 * how often it has been met. Nothing shows while it loads, when there is no word yet, or when the request fails: it is a nice extra, never the reason a page breaks. */
export function WordOfTheDay() {
  const { t } = useI18n();
  const { user } = useAuth();
  const { active } = useActiveLanguage();
  const today = useQuery({ queryKey: wordsKey(user!.id, active, "today"), queryFn: () => api.wordOfTheDay(active), staleTime: 10 * 60 * 1000 });
  const word = today.data?.word;
  if (!word) return null;
  const met = word.exposure?.met ?? 0;
  return (
    <section className="mb-8" aria-labelledby="word-of-the-day"><Card>
      <p id="word-of-the-day" className="text-sm font-medium text-slate-600">{t("exposure.today.title")}</p>
      <div className="mt-3 flex flex-wrap items-center gap-4">
        <PictureButton word={word} language={active} />
        <div className="min-w-0 flex-1">
          <p className="text-2xl font-semibold tracking-tight text-slate-900"><span lang={active}>{word.word}</span> <SpeakButton text={word.word} language={active} /></p>
          <p className="text-slate-700">{word.meaning || <span className="text-slate-600">{t("exposure.today.noMeaning")}</span>}</p>
          <p className="mt-1 text-xs text-slate-600">{t("exposure.today.hint")} {met > 0 ? t("exposure.today.met", { count: met }) : t("exposure.today.fresh")}</p>
        </div>
        <Link to="/practice" className="rounded-lg border border-slate-300 bg-surface px-3.5 py-2 text-sm font-medium text-slate-700 shadow-xs hover:bg-slate-100/70">{t("exposure.today.practise")}</Link>
      </div>
    </Card></section>
  );
}
