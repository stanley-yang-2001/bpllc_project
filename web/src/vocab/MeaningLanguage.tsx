import { useActiveLanguage } from "../auth/ActiveLanguage";
import { useAuth } from "../auth/AuthContext";
import { inputCls } from "../components/ui";
import { useI18n } from "../i18n/I18nProvider";
import { usePreferences } from "../prefs/PreferencesProvider";

/** Which language the tutor writes meanings in: the learner's own, the one they study, or both. Saved on the account. */
export function MeaningLanguage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const { active, info } = useActiveLanguage();
  const { prefs, update } = usePreferences();
  const nativeCode = user?.native_language ?? "en";
  const native = info(nativeCode)?.native ?? nativeCode;
  const study = info(active)?.native ?? active;
  const same = nativeCode === active;                  // studying your own language: "both" would just repeat it
  const value = same && prefs.meaning_mode === "both" ? "native" : prefs.meaning_mode;
  return (
    <label className="flex items-center gap-2 text-sm text-slate-700">
      <span className="whitespace-nowrap">{t("vocab.meaningIn")}</span>
      <select className={`${inputCls} w-auto`} value={value} onChange={(e) => void update({ meaning_mode: e.target.value as "native" | "study" | "both" })}>
        <option value="native">{t("vocab.meaningNative", { language: native })}</option>
        <option value="study">{t("vocab.meaningStudy", { language: study })}</option>
        {!same && <option value="both">{t("vocab.meaningBoth", { native, study })}</option>}
      </select>
    </label>
  );
}
