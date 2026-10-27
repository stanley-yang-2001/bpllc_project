import { useMutation } from "@tanstack/react-query";
import { Languages } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { useAuth } from "../auth/AuthContext";
import { Button, ErrorText, inputCls } from "../components/ui";
import { useI18n } from "../i18n/I18nProvider";
import { chunks } from "../speech/speak";

/** Translate some lines (a story) or some words into another site language. The result is shown, never saved. `texts` are sent
 * as they are; for a story the caller passes chunks(story). The target defaults to the learner's own language when it differs. */
export function TranslateBox({ language, texts, words = false, idPrefix }: { language: string; texts: string[]; words?: boolean; idPrefix: string }) {
  const { user } = useAuth();
  const { all } = useActiveLanguage();
  const { t, err } = useI18n();
  const options = all.filter((l) => l.code !== language);
  const preferred = options.find((l) => l.code === user?.native_language)?.code ?? options.find((l) => l.code === "en")?.code ?? options[0]?.code ?? "";
  const [target, setTarget] = useState(preferred);
  const run = useMutation({ mutationFn: () => api.translate({ language, target_language: target, texts, words }) });
  useEffect(() => { run.reset(); }, [language, target, texts.join("\n")]);          // a result belongs to one text and one target
  useEffect(() => { if (!options.some((l) => l.code === target)) setTarget(preferred); }, [language]);

  return (
    <div className="space-y-3 rounded-lg border border-slate-200 p-3">
      <div className="flex flex-wrap items-end gap-2">
        <div>
          <label htmlFor={`${idPrefix}-target`} className="mb-1 block text-xs font-medium text-slate-700">{t("translate.into")}</label>
          <select id={`${idPrefix}-target`} className={`${inputCls} w-auto`} value={target} onChange={(e) => setTarget(e.target.value)}>
            {options.map((l) => <option key={l.code} value={l.code} lang={l.code}>{l.native}</option>)}
          </select>
        </div>
        <Button onClick={() => run.mutate()} loading={run.isPending} disabled={!target || texts.length === 0} icon={<Languages aria-hidden className="size-4" />}>
          {run.isPending ? t("translate.loading") : t("translate.go")}
        </Button>
      </div>
      <p className="text-xs text-slate-600">{t("translate.hint")}</p>
      <ErrorText>{run.error ? err(run.error) : undefined}</ErrorText>
      {run.data && (
        <ul className="space-y-2" aria-label={t("translate.open")}>
          {run.data.items.map((item, i) => (
            <li key={i} className="text-sm">
              <span lang={language} className="block text-slate-600">{item.text}</span>
              <span lang={run.data!.target_language} className="block text-slate-900">{item.translation ?? t("translate.missing")}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export const storyLines = (story: string) => chunks(story).slice(0, 60);
