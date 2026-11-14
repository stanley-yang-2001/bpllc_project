import { Headphones } from "lucide-react";
import { useI18n } from "../../i18n/I18nProvider";
import { Button } from "../../components/ui";
import { speechSupported, voiceFor } from "../../speech/speak";
import { useVoices } from "../../speech/useVoices";
import { Dictation } from "../Dictation";
import { ModeTile } from "./ModeTile";
import type { PracticeMode } from "./types";

export const DictationMode: PracticeMode<"dictation"> = {
  Tile({ ctx, start }) {
    const { t } = useI18n();
    useVoices();                                                      // re-render when the device finishes loading its voices
    const canSpeak = speechSupported();
    const noVoice = canSpeak && voiceFor(ctx.language) === null;      // the device lists voices but none fit this language (undefined = not loaded yet)
    return (
      <ModeTile icon={Headphones} title={t("practice.dictation.title")} text={t("practice.dictation.text")}>
        {!canSpeak || noVoice
          ? <p role="status" className="text-sm text-slate-600">{canSpeak ? t("practice.dictation.noVoice", { language: ctx.name }) : t("practice.dictation.noSpeech")}</p>
          : <Button onClick={() => start({ mode: "dictation" })}>{t("practice.dictation.start")}</Button>}
      </ModeTile>
    );
  },
  Session: ({ ctx, onDone }) => <Dictation language={ctx.language} set={ctx.set} due={ctx.dueOnly} onDone={onDone} />,
};
