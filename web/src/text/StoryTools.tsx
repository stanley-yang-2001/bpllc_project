import { Languages, Type } from "lucide-react";
import { useState } from "react";
import { Button } from "../components/ui";
import { useI18n } from "../i18n/I18nProvider";
import { SpeakButton } from "../speech/SpeakButton";
import { PronunciationLines } from "./PronunciationLines";
import { storyLines, TranslateBox } from "./TranslateBox";

/** What a learner can do with a story: hear it, see how it is pronounced, translate it. Used in Studio, Library and Chat. */
export function StoryTools({ text, language, id }: { text: string; language: string; id: string }) {
  const { t } = useI18n();
  const [reading, setReading] = useState(false);
  const [translating, setTranslating] = useState(false);
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-1">
        <SpeakButton text={text} language={language} label={t("speech.listen")} slow />
        <Button type="button" variant="ghost" aria-pressed={reading} onClick={() => setReading(!reading)} icon={<Type aria-hidden className="size-4" />}>
          {reading ? t("reading.hide") : t("reading.show")}
        </Button>
        <Button type="button" variant="ghost" aria-pressed={translating} onClick={() => setTranslating(!translating)} icon={<Languages aria-hidden className="size-4" />}>
          {translating ? t("translate.close") : t("translate.open")}
        </Button>
      </div>
      {reading && <PronunciationLines text={text} language={language} />}
      {translating && <TranslateBox language={language} texts={storyLines(text)} idPrefix={`${id}-translate`} />}
    </div>
  );
}
