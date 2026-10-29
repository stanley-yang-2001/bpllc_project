import { useState } from "react";
import { Volume2 } from "lucide-react";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { useAuth } from "../auth/AuthContext";
import { Button, inputCls } from "../components/ui";
import { useI18n } from "../i18n/I18nProvider";
import { chooseVoice, chosenVoiceName, NORMAL_RATE, SAMPLE_TEXT, speak, speechSupported, voicesFor } from "../speech/speak";
import { useVoices } from "../speech/useVoices";
import { Section } from "./Section";

/** Which voice reads each studied language aloud. Voices belong to the device and browser, so the choice is kept on this device only. */
export function VoiceSection() {
  const { t } = useI18n();
  const { user } = useAuth();
  const { info } = useActiveLanguage();
  const voices = useVoices();
  const [picked, setPicked] = useState<Record<string, string>>({});
  const [missing, setMissing] = useState<string | null>(null);
  if (!speechSupported()) {
    return <Section title={t("voices.title")}><p className="text-sm text-slate-600">{t("voices.unsupported")}</p></Section>;
  }
  return (
    <Section title={t("voices.title")} description={t("voices.description")}>
      <ul className="space-y-4">
        {(user?.languages ?? []).map((code) => {
          const name = info(code)?.native ?? code;
          const options = voicesFor(code, voices);
          const value = picked[code] ?? chosenVoiceName(code);
          const id = `voice-${code}`;
          return (
            <li key={code}>
              <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-slate-700"><span lang={code}>{name}</span></label>
              <div className="flex flex-wrap items-center gap-2">
                <select id={id} aria-label={t("voices.pick", { language: name })} className={`${inputCls} w-auto max-w-full`} value={options.some((v) => v.name === value) ? value : ""} disabled={options.length === 0}
                  onChange={(e) => { chooseVoice(code, e.target.value); setPicked({ ...picked, [code]: e.target.value }); }}>
                  <option value="">{t("voices.auto")}</option>
                  {options.map((v) => <option key={v.name} value={v.name}>{v.name} ({v.lang})</option>)}
                </select>
                <Button type="button" variant="secondary" disabled={options.length === 0} icon={<Volume2 aria-hidden className="size-4" />}
                  onClick={() => { setMissing(null); speak(SAMPLE_TEXT[code] ?? SAMPLE_TEXT.en, code, NORMAL_RATE, { onNoVoice: () => setMissing(code) }); }}>{t("voices.test")}</Button>
              </div>
              {(options.length === 0 || missing === code) && voices.length > 0 && <p role="status" className="mt-1.5 text-xs text-slate-600">{t("speech.noVoice")}</p>}
            </li>
          );
        })}
      </ul>
    </Section>
  );
}
