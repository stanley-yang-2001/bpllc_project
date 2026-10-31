import { SendHorizontal } from "lucide-react";
import { useState } from "react";
import { nothingTicked, SetPicker, type SetChoice } from "../components/SetPicker";
import { Button, inputCls } from "../components/ui";
import { useI18n } from "../i18n/I18nProvider";
import { MAX_CHARS } from "./ChatContext";

/** The set choice, the message box and Send. It hands the text up and clears itself; Enter sends, Shift+Enter adds a line. */
export function Composer({ language, sets, onSets, sending, onSend }: { language: string; sets: SetChoice; onSets: (s: SetChoice) => void; sending: boolean; onSend: (text: string) => void }) {
  const { t } = useI18n();
  const [text, setText] = useState("");
  const blocked = sending || !text.trim() || nothingTicked(sets);
  const submit = () => {
    if (blocked) return;
    onSend(text);
    setText("");
  };
  return (
    <div>
      <div className="mb-3"><SetPicker language={language} value={sets} onChange={onSets} idPrefix="chat-set" /></div>
      <label htmlFor="chat-message" className="sr-only">{t("chat.message")}</label>
      <div className="flex items-end gap-2">
        <textarea
          id="chat-message"
          aria-label={t("chat.message")}
          className={`${inputCls} resize-none`}
          rows={2}
          maxLength={MAX_CHARS}
          placeholder={t("chat.placeholder")}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {   // Enter also confirms an input-method choice
              e.preventDefault();
              submit();
            }
          }}
        />
        <Button onClick={submit} disabled={blocked} icon={<SendHorizontal aria-hidden className="size-4" />}>{t("common.send")}</Button>
      </div>
      <p className="mt-2 text-xs text-slate-600">{t("chat.disclaimer")}</p>
    </div>
  );
}
