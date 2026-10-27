import { useI18n } from "../i18n/I18nProvider";
import { usePreferences } from "../prefs/PreferencesProvider";
import { Section } from "./Section";

export function SiteLanguageSection() {
  const { prefs, update, saveFailed } = usePreferences();
  const { t } = useI18n();
  return (
    <Section title={t("settings.site.title")} description={t("settings.site.description")}>
      <label className="flex cursor-pointer items-start gap-2.5 text-sm text-slate-800">
        <input type="checkbox" className="mt-0.5 size-4 rounded accent-brand-600" checked={prefs.ui_follows_study_language}
          onChange={(e) => void update({ ui_follows_study_language: e.target.checked })} />
        {t("settings.site.checkbox")}
      </label>
      <label className="mt-3 flex cursor-pointer items-start gap-2.5 text-sm text-slate-800">
        <input type="checkbox" className="mt-0.5 size-4 rounded accent-brand-600" checked={prefs.chat_in_study_language}
          onChange={(e) => void update({ chat_in_study_language: e.target.checked })} />
        <span>{t("settings.site.chatCheckbox")}<span className="mt-0.5 block text-xs text-slate-600">{t("settings.site.chatHint")}</span></span>
      </label>
      {saveFailed && <p role="status" className="mt-3 text-sm text-amber-800 dark:text-amber-200">{t("settings.site.saveFailed")}</p>}
    </Section>
  );
}
