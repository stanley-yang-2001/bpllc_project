import { Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { ApiError, type StoryOptions } from "../api/client";
import { SetPicker } from "../components/SetPicker";
import { Button, ErrorText, inputCls } from "../components/ui";
import { useI18n } from "../i18n/I18nProvider";
import { topicLabel, typeLabel } from "../i18n/labels";
import { DifficultyPicker } from "./DifficultyPicker";
import { CLASSIC, CUSTOM, CUSTOM_MAX, CUSTOM_TOPIC } from "./labels";
import type { StoryChoices } from "./useStoryChoices";
import type { StoryGeneration } from "./useStoryGeneration";

/** The kind, topic and difficulty pickers, the sets, and the Make button with its errors. */
export function OptionsForm({ language, options, c, g, onMake }: { language: string; options: StoryOptions | undefined; c: StoryChoices; g: StoryGeneration; onMake: () => void }) {
  const { t, err } = useI18n();
  const { generate } = g;
  const failure = generate.error instanceof ApiError ? generate.error : null;
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="story-type" className="mb-1 block text-sm font-medium text-slate-700">{t("studio.kind")}</label>
          <select id="story-type" className={inputCls} value={c.type} onChange={(e) => c.setType(e.target.value)}>
            <option value="">{t("studio.surprise")}</option>
            {options?.types.map((ty) => <option key={ty} value={ty}>{typeLabel(t, ty)}</option>)}
            <option value={CUSTOM}>{t("studio.kindCustom")}</option>
          </select>
          {c.type === CUSTOM && (
            <div className="mt-2">
              <label htmlFor="story-custom" className="mb-1 block text-sm font-medium text-slate-700">{t("studio.customLabel")}</label>
              <input
                id="story-custom" className={inputCls} value={c.custom} maxLength={CUSTOM_MAX} lang={language}
                onChange={(e) => c.setCustom(e.target.value)} aria-describedby="story-custom-hint"
                aria-invalid={c.custom.trim() !== "" && c.customBad}
              />
              <p id="story-custom-hint" className={`mt-1 text-xs ${c.custom.trim() !== "" && c.customBad ? "text-red-700" : "text-slate-600"}`}>{t("studio.customHint")}</p>
            </div>
          )}
        </div>
        <div>
          <label htmlFor="story-topic" className="mb-1 block text-sm font-medium text-slate-700">{t("studio.topic")}</label>
          <select id="story-topic" className={inputCls} value={c.topic} onChange={(e) => c.setTopic(e.target.value)} disabled={!c.kind || CLASSIC.includes(c.kind)}>
            <option value="">{t("studio.anyTopic")}</option>
            {options?.topics.map((tp) => <option key={tp} value={tp}>{topicLabel(t, tp)}</option>)}
            <option value={CUSTOM_TOPIC}>{t("studio.kindCustom")}</option>
          </select>
          {c.topicOn && c.topic === CUSTOM_TOPIC && (
            <div className="mt-2">
              <label htmlFor="story-topic-custom" className="mb-1 block text-sm font-medium text-slate-700">{t("studio.topicCustomLabel")}</label>
              <input
                id="story-topic-custom" className={inputCls} value={c.customTopic} maxLength={CUSTOM_MAX} lang={language}
                onChange={(e) => c.setCustomTopic(e.target.value)} aria-describedby="story-topic-custom-hint"
                aria-invalid={c.customTopic.trim() !== "" && c.topicBad}
              />
              <p id="story-topic-custom-hint" className={`mt-1 text-xs ${c.customTopic.trim() !== "" && c.topicBad ? "text-red-700" : "text-slate-600"}`}>{t("studio.topicCustomHint")}</p>
            </div>
          )}
          {(!c.kind || CLASSIC.includes(c.kind)) && <p className="mt-1 text-xs text-slate-600">{t("studio.topicHint")}</p>}
        </div>
      </div>
      <DifficultyPicker d={c.difficulty} />
      <SetPicker language={language} value={c.sets} onChange={c.setSets} idPrefix="studio-set" />
      <div>
        <Button onClick={onMake} loading={generate.isPending} disabled={!c.canMake} icon={<Sparkles aria-hidden className="size-4" />}>
          {generate.isPending ? t("studio.writing") : t("studio.make")}
        </Button>
        {generate.isPending && <p role="status" className="mt-2 text-sm text-slate-600">{t("studio.wait")}</p>}
        {failure && (
          <ErrorText>
            {err(failure)}
            {failure.code === "not_enough_words" && <> <Link to="/vocabulary" className="font-medium underline">{t("studio.goVocab")}</Link>.</>}
          </ErrorText>
        )}
        {generate.error && !failure && <ErrorText>{err(generate.error)}</ErrorText>}
      </div>
    </>
  );
}
