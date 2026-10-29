import { BookOpen, Layers, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { useI18n } from "../i18n/I18nProvider";
import { Card } from "../components/ui";
import { StarterPacks } from "./StarterPacks";

/** For someone with an empty list: three steps, and the starter packs right here so step one is one click. */
export function FirstRunGuide({ language, onAdded }: { language: string; onAdded: () => void }) {
  const { t } = useI18n();
  const link = "font-medium text-brand-600 underline dark:text-brand-200";
  return (
    <section className="mb-8 space-y-4" aria-labelledby="guide-title">
      <Card className="space-y-4">
        <h2 id="guide-title" className="text-lg font-semibold text-slate-900">{t("guide.title")}</h2>
        <ol className="grid gap-4 sm:grid-cols-3">
          <li className="space-y-1"><p className="flex items-center gap-2 font-medium text-slate-900"><BookOpen aria-hidden className="size-4" />{t("guide.step1")}</p><p className="text-sm text-slate-600">{t("guide.step1.text")}</p></li>
          <li className="space-y-1"><p className="flex items-center gap-2 font-medium text-slate-900"><Sparkles aria-hidden className="size-4" />{t("guide.step2")}</p><p className="text-sm text-slate-600">{t("guide.step2.text")}</p></li>
          <li className="space-y-1"><p className="flex items-center gap-2 font-medium text-slate-900"><Layers aria-hidden className="size-4" />{t("guide.step3")}</p><p className="text-sm text-slate-600">{t("guide.step3.text")}</p></li>
        </ol>
        <p className="text-sm"><Link to="/vocabulary" className={link}>{t("home.addFirst")}</Link></p>
      </Card>
      <StarterPacks language={language} onAdded={onAdded} linkToVocabulary />
    </section>
  );
}
