import { useQuery } from "@tanstack/react-query";
import { Download, LogOut, Monitor, Moon, Palette, RefreshCw, Sun, Trash2 } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api, type Health } from "../api/client";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { useAuth } from "../auth/AuthContext";
import { Modal } from "../components/Modal";
import { useToast } from "../components/Toast";
import { Badge, Button, Card, ErrorText, inputCls, PageHeader, Skeleton } from "../components/ui";
import { useI18n } from "../i18n/I18nProvider";
import type { MessageKey } from "../i18n/messages";
import { usePreferences } from "../prefs/PreferencesProvider";
import { ColorWheel } from "../theme/ColorWheel";
import { contrast } from "../theme/color";
import { DEFAULT_CUSTOM, derivePalette, PARTS, PRESET_IDS, PRESETS, type Colors, type PresetId } from "../theme/palette";
import { useTheme, type Theme } from "../theme/ThemeProvider";

function Section({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <Card>
      <h2 className="font-semibold text-slate-900">{title}</h2>
      {description && <p className="mt-1 text-sm text-slate-600">{description}</p>}
      <div className="mt-4">{children}</div>
    </Card>
  );
}

const Label = ({ htmlFor, children }: { htmlFor: string; children: ReactNode }) => (
  <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium text-slate-700">{children}</label>
);

function ProfileSection() {
  const { user, setUser } = useAuth();
  const { all } = useActiveLanguage();
  const toast = useToast();
  const { t, err: errText } = useI18n();
  const [name, setName] = useState(user?.display_name ?? "");
  const [native, setNative] = useState(user?.native_language ?? "en");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const dirty = name.trim() !== user?.display_name || native !== user?.native_language;

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(undefined);
    try {
      setUser(await api.updateProfile({ display_name: name.trim(), native_language: native }));
      toast(t("settings.profile.saved"));
    } catch (err) { setError(errText(err)); } finally { setBusy(false); }
  };
  return (
    <Section title={t("settings.profile.title")} description={t("settings.profile.description")}>
      <form onSubmit={save} className="grid gap-4 sm:grid-cols-2" aria-label={t("settings.form.profile")}>
        <div>
          <Label htmlFor="p-name">{t("settings.profile.name")}</Label>
          <input id="p-name" className={inputCls} value={name} maxLength={40} onChange={(e) => setName(e.target.value)} autoComplete="name" />
        </div>
        <div>
          <Label htmlFor="p-native">{t("settings.profile.native")}</Label>
          <select id="p-native" className={inputCls} value={native} onChange={(e) => setNative(e.target.value)}>
            {all.map((l) => <option key={l.code} value={l.code} lang={l.code}>{l.native}</option>)}
          </select>
        </div>
        <div className="sm:col-span-2">
          <Button type="submit" loading={busy} disabled={!dirty || !name.trim()}>{t("settings.profile.save")}</Button>
          <ErrorText>{error}</ErrorText>
        </div>
      </form>
    </Section>
  );
}

function EmailSection() {
  const { user, setUser } = useAuth();
  const toast = useToast();
  const { t, err: errText } = useI18n();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(undefined);
    try {
      setUser(await api.changeEmail({ email, password }));
      setEmail(""); setPassword("");
      toast(t("settings.email.changed"));
    } catch (err) { setError(errText(err)); } finally { setBusy(false); }
  };
  return (
    <Section title={t("settings.email.title")} description={t("settings.email.description")}>
      <p className="mb-4 text-sm text-slate-600">{t("settings.email.current")} <strong className="text-slate-900">{user?.email}</strong></p>
      <form onSubmit={save} className="grid gap-4 sm:grid-cols-2" aria-label={t("settings.form.email")}>
        <div>
          <Label htmlFor="e-new">{t("settings.email.new")}</Label>
          <input id="e-new" type="email" autoComplete="email" className={inputCls} value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="e-pass">{t("settings.email.password")}</Label>
          <input id="e-pass" type="password" autoComplete="current-password" className={inputCls} value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <div className="sm:col-span-2">
          <Button type="submit" variant="secondary" loading={busy} disabled={!email || !password}>{t("settings.email.change")}</Button>
          <ErrorText>{error}</ErrorText>
        </div>
      </form>
    </Section>
  );
}

function PasswordSection() {
  const toast = useToast();
  const { t, err: errText } = useI18n();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const mismatch = again !== "" && again !== next;
  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(undefined);
    try {
      await api.changePassword({ current_password: current, new_password: next });
      setCurrent(""); setNext(""); setAgain("");
      toast(t("settings.password.changed"));
    } catch (err) { setError(errText(err)); } finally { setBusy(false); }
  };
  return (
    <Section title={t("settings.password.title")} description={t("settings.password.description")}>
      <form onSubmit={save} className="grid gap-4 sm:grid-cols-3" aria-label={t("settings.form.password")}>
        <div>
          <Label htmlFor="pw-cur">{t("settings.password.current")}</Label>
          <input id="pw-cur" type="password" autoComplete="current-password" className={inputCls} value={current} onChange={(e) => setCurrent(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="pw-new">{t("settings.password.new")}</Label>
          <input id="pw-new" type="password" autoComplete="new-password" className={inputCls} value={next} onChange={(e) => setNext(e.target.value)} />
          <p className="mt-1 text-xs text-slate-500">{t("settings.password.min")}</p>
        </div>
        <div>
          <Label htmlFor="pw-again">{t("settings.password.again")}</Label>
          <input id="pw-again" type="password" autoComplete="new-password" className={inputCls} value={again} onChange={(e) => setAgain(e.target.value)} />
          <ErrorText>{mismatch ? t("settings.password.mismatch") : undefined}</ErrorText>
        </div>
        <div className="sm:col-span-3">
          <Button type="submit" variant="secondary" loading={busy} disabled={!current || next.length < 8 || next !== again}>{t("settings.password.change")}</Button>
          <ErrorText>{error}</ErrorText>
        </div>
      </form>
    </Section>
  );
}

const BUILT_INS: { value: Theme; label: MessageKey; icon: typeof Sun }[] = [
  { value: "light", label: "settings.appearance.light", icon: Sun },
  { value: "dark", label: "settings.appearance.dark", icon: Moon },
  { value: "system", label: "settings.appearance.system", icon: Monitor },
];
const PRESET_LABEL: Record<PresetId, MessageKey> = {
  ocean: "theme.preset.ocean", forest: "theme.preset.forest", sunset: "theme.preset.sunset", rose: "theme.preset.rose",
  midnight: "theme.preset.midnight", graphite: "theme.preset.graphite", contrast: "theme.preset.contrast",
};
const PART_LABEL: Record<(typeof PARTS)[number], MessageKey> = {
  page: "settings.custom.page", cards: "settings.custom.cards", text: "settings.custom.text",
  borders: "settings.custom.borders", accent: "settings.custom.accent",
};
/** The built-in Light and Dark as five colours, so "Start from" can offer them too. */
const LIGHT_COLORS: Colors = { page: "#f8fafc", cards: "#ffffff", text: "#0f172a", borders: "#e2e8f0", accent: "#4f46e5" };
const DARK_COLORS: Colors = { page: "#020617", cards: "#0f172a", text: "#f8fafc", borders: "#2a374d", accent: "#4f46e5" };

/** A tile: a radio with a small preview of the theme's page, card, accent and text colours. */
function Tile({ value, label, current, onPick, preview, icon: Icon }: {
  value: Theme; label: string; current: Theme; onPick: () => void; preview?: Colors; icon?: typeof Sun;
}) {
  const on = current === value;
  return (
    <label className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm transition has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-brand-500 ${
      on ? "border-brand-500 bg-surface font-medium text-slate-900 shadow-xs" : "border-slate-200 text-slate-600 hover:border-slate-300 hover:text-slate-900"
    }`}>
      <input type="radio" name="theme" value={value} checked={on} onChange={onPick} className="sr-only" />
      {preview ? (
        <span aria-hidden className="flex size-6 shrink-0 overflow-hidden rounded-md border border-slate-300" style={{ background: preview.page }}>
          <span className="m-auto size-3 rounded-sm" style={{ background: preview.cards, boxShadow: `inset 0 -3px 0 ${preview.accent}`, border: `1px solid ${preview.borders}` }} />
        </span>
      ) : Icon ? <Icon aria-hidden className="size-4 shrink-0" /> : null}
      {label}
    </label>
  );
}

function ratioLine(label: string, ratio: number, t: (k: MessageKey) => string) {
  const good = ratio >= 4.5;
  return (
    <li key={label} className="flex items-center justify-between gap-3">
      <span>{label}</span>
      <span className="flex items-center gap-2">
        <span className="tabular-nums">{ratio.toFixed(1)}:1</span>
        <Badge tone={good ? "good" : "bad"}>{good ? t("settings.custom.good") : t("settings.custom.hard")}</Badge>
      </span>
    </li>
  );
}

function CustomEditor() {
  const { customColors, setCustomColors, palette, theme } = useTheme();
  const { t } = useI18n();
  const [part, setPart] = useState<(typeof PARTS)[number]>("page");
  const colors = customColors;
  const shown = theme === "custom" ? palette : derivePalette(colors);
  const accentUsed = shown?.vars["--color-brand-600"] ?? colors.accent;
  const partName = t(PART_LABEL[part]);
  const starts: { id: string; label: string; colors: Colors }[] = [
    { id: "light", label: t("settings.appearance.light"), colors: LIGHT_COLORS },
    { id: "dark", label: t("settings.appearance.dark"), colors: DARK_COLORS },
    ...PRESET_IDS.map((id) => ({ id, label: t(PRESET_LABEL[id]), colors: PRESETS[id].colors as Colors })),
  ];
  return (
    <div className="mt-5 border-t border-slate-200 pt-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-medium text-slate-900">{t("settings.custom.title")}</h3>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          {t("settings.custom.startFrom")}
          <select className={`${inputCls} w-auto`} value="" onChange={(e) => { const s = starts.find((x) => x.id === e.target.value); if (s) setCustomColors(s.colors); }}>
            <option value="" />
            {starts.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
        </label>
      </div>
      <fieldset className="mt-4">
        <legend className="mb-2 text-sm font-medium text-slate-700">{t("settings.custom.part")}</legend>
        <div className="flex flex-wrap gap-2">
          {PARTS.map((p) => (
            <label key={p} className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-1.5 text-sm has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-brand-500 ${part === p ? "border-brand-500 bg-surface font-medium text-slate-900" : "border-slate-200 text-slate-600"}`}>
              <input type="radio" name="custom-part" className="sr-only" checked={part === p} onChange={() => setPart(p)} />
              <span aria-hidden className="size-3.5 rounded-full border border-slate-400" style={{ background: colors[p] }} />
              {t(PART_LABEL[p])}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="mt-4">
        <ColorWheel
          value={colors[part]}
          onChange={(hex) => setCustomColors({ ...colors, [part]: hex })}
          label={t("settings.custom.wheel", { part: partName })}
          brightnessLabel={t("settings.custom.brightness")}
          hexLabel={t("settings.custom.hex")}
          spoken={(h, s) => t("settings.custom.wheelSpoken", { hue: Math.round(h), strength: Math.round(s * 100) })}
        />
      </div>
      <div className="mt-5">
        <h4 className="text-sm font-medium text-slate-900">{t("settings.custom.readability")}</h4>
        <ul className="mt-2 max-w-sm space-y-1.5 text-sm text-slate-700">
          {ratioLine(t("settings.custom.textOnPage"), contrast(colors.text, colors.page), t)}
          {ratioLine(t("settings.custom.textOnCards"), contrast(colors.text, colors.cards), t)}
          {ratioLine(t("settings.custom.buttonText"), contrast("#ffffff", accentUsed), t)}
        </ul>
        {shown?.accentDarkened && <p className="mt-2 text-xs text-slate-600">{t("settings.custom.darkened")}</p>}
        <Button variant="secondary" className="mt-3" onClick={() => setCustomColors(DEFAULT_CUSTOM)}>{t("settings.custom.reset")}</Button>
      </div>
    </div>
  );
}

function AppearanceSection() {
  const { theme, setTheme } = useTheme();
  const { saveFailed, loggedIn } = usePreferences();
  const { t } = useI18n();
  return (
    <Section title={t("settings.appearance.title")} description={t("settings.appearance.description")}>
      <div role="radiogroup" aria-label={t("settings.appearance.theme")} className="flex flex-wrap gap-2">
        {BUILT_INS.map(({ value, label, icon }) => <Tile key={value} value={value} label={t(label)} current={theme} icon={icon} onPick={() => setTheme(value)} />)}
        {PRESET_IDS.map((id) => <Tile key={id} value={id} label={t(PRESET_LABEL[id])} current={theme} preview={PRESETS[id].colors} onPick={() => setTheme(id)} />)}
        <Tile value="custom" label={t("theme.custom")} current={theme} onPick={() => setTheme("custom")} icon={Palette} />
      </div>
      {loggedIn && theme === "custom" && <CustomEditor />}
      {saveFailed && (
        <p role="status" className="mt-3 text-sm text-amber-800 dark:text-amber-200">
          {t("settings.appearance.saveFailed")}
        </p>
      )}
    </Section>
  );
}

function SiteLanguageSection() {
  const { prefs, update, saveFailed } = usePreferences();
  const { t } = useI18n();
  return (
    <Section title={t("settings.site.title")} description={t("settings.site.description")}>
      <label className="flex cursor-pointer items-start gap-2.5 text-sm text-slate-800">
        <input type="checkbox" className="mt-0.5 size-4 rounded accent-brand-600" checked={prefs.ui_follows_study_language}
          onChange={(e) => void update({ ui_follows_study_language: e.target.checked })} />
        {t("settings.site.checkbox")}
      </label>
      {saveFailed && <p role="status" className="mt-3 text-sm text-amber-800 dark:text-amber-200">{t("settings.site.saveFailed")}</p>}
    </Section>
  );
}

function DeleteAccountModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { deleteAccount } = useAuth();
  const { t, err: errText } = useI18n();
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const close = () => { setPassword(""); setError(undefined); onClose(); };
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(undefined);
    try {
      await deleteAccount(password);          // on success the whole screen is cleared and you land on the login page
    } catch (err) { setError(errText(err)); setBusy(false); }
  };
  return (
    <Modal open={open} onClose={close} title={t("settings.delete.title")}>
      <form onSubmit={submit}>
        <p className="text-sm text-slate-600">{t("settings.delete.intro")}</p>
        <ul className="mt-2 list-disc space-y-0.5 pl-5 text-sm text-slate-600">
          <li>{t("settings.delete.item1")}</li>
          <li>{t("settings.delete.item2")}</li>
          <li>{t("settings.delete.item3")}</li>
          <li>{t("settings.delete.item4")}</li>
          <li>{t("settings.delete.item5")}</li>
          <li>{t("settings.delete.item6")}</li>
        </ul>
        <p className="mt-3 text-sm text-slate-600">{t("settings.delete.consider")}</p>
        <div className="mt-4">
          <Label htmlFor="del-pass">{t("settings.delete.password")}</Label>
          <input id="del-pass" type="password" autoComplete="current-password" className={inputCls} value={password} onChange={(e) => setPassword(e.target.value)} data-autofocus />
          <ErrorText>{error}</ErrorText>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={close}>{t("common.cancel")}</Button>
          <Button type="submit" variant="danger" loading={busy} disabled={!password} icon={<Trash2 aria-hidden className="size-4" />}>{t("settings.delete.submit")}</Button>
        </div>
      </form>
    </Modal>
  );
}

function DataSection() {
  const toast = useToast();
  const { t, err: errText } = useI18n();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [confirmOpen, setConfirmOpen] = useState(false);

  const download = async () => {
    setBusy(true); setError(undefined);
    try {
      const data = await api.exportData();
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `language-tutor-my-data-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast(t("settings.data.downloaded"));
    } catch (err) { setError(errText(err)); } finally { setBusy(false); }
  };
  return (
    <Section title={t("settings.data.title")} description={t("settings.data.description")}>
      <p className="mb-4 text-sm text-slate-600">
        {t("settings.data.intro")}{" "}
        <Link to="/privacy" className="font-medium text-brand-600 underline underline-offset-2 dark:text-brand-200">{t("layout.privacy")}</Link>
      </p>
      <div className="flex flex-wrap gap-3">
        <Button variant="secondary" onClick={() => void download()} loading={busy} icon={<Download aria-hidden className="size-4" />}>{t("settings.data.download")}</Button>
        <Button variant="danger" onClick={() => setConfirmOpen(true)} icon={<Trash2 aria-hidden className="size-4" />}>{t("settings.data.delete")}</Button>
      </div>
      <ErrorText>{error}</ErrorText>
      <DeleteAccountModal open={confirmOpen} onClose={() => setConfirmOpen(false)} />
    </Section>
  );
}

function Row({ label, check }: { label: string; check: Health["postgres"] }) {
  const { t } = useI18n();
  const state = check.ok === true ? t("settings.services.ok") : check.ok === false ? `${t("settings.services.problem")}${check.detail ? ` (${check.detail})` : ""}`
    : check.status === "stub" ? t("settings.services.stub") : t("settings.services.unchecked");
  const dot = check.ok === true ? "bg-emerald-500" : check.ok === false ? "bg-red-500" : "bg-slate-300";
  return (
    <li className="flex items-center justify-between border-b border-slate-100 py-3 last:border-0">
      <span className="flex items-center gap-2.5 text-sm text-slate-800">
        <span aria-hidden className={`size-2.5 rounded-full ${dot}`} />
        {label}
      </span>
      <span className="text-sm text-slate-600">{state}</span>
    </li>
  );
}

export default function Settings() {
  const { user, logoutAll } = useAuth();
  const { t, err: errText } = useI18n();
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, staleTime: 0 });
  return (
    <div>
      <PageHeader title={t("nav.settings")} description={t("settings.description")} />
      <div className="space-y-6">
        <Card>
          <h2 className="mb-3 font-semibold text-slate-900">{t("settings.account")}</h2>
          <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-[8rem_1fr]">
            <dt className="text-slate-500">{t("settings.email")}</dt>
            <dd className="font-medium text-slate-900">{user?.email}</dd>
            <dt className="text-slate-500">{t("settings.languages")}</dt>
            <dd className="flex flex-wrap gap-1.5">{user?.languages.map((l) => <Badge key={l} tone="brand">{l.toUpperCase()}</Badge>)}</dd>
          </dl>
        </Card>
        <ProfileSection />
        <EmailSection />
        <PasswordSection />
        <AppearanceSection />
        <SiteLanguageSection />
        <DataSection />

        <Card>
          <div className="mb-2 flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">{t("settings.services.title")}</h2>
            <Button variant="secondary" onClick={() => void health.refetch()} loading={health.isFetching} icon={<RefreshCw aria-hidden className="size-4" />}>{t("settings.services.recheck")}</Button>
          </div>
          {health.isPending ? (
            <div className="space-y-3 py-2"><Skeleton className="h-5 w-full" /><Skeleton className="h-5 w-full" /><Skeleton className="h-5 w-full" /></div>
          ) : health.isError ? (
            <ErrorText>{errText(health.error)}</ErrorText>
          ) : (
            <ul>
              <Row label="Postgres" check={health.data.postgres} />
              <Row label={t("settings.services.langflow")} check={health.data.langflow} />
              <Row label={t("settings.services.groq")} check={health.data.groq} />
            </ul>
          )}
        </Card>

        <Section title={t("settings.signins.title")} description={t("settings.signins.description")}>
          <Button variant="secondary" onClick={() => void logoutAll()} icon={<LogOut aria-hidden className="size-4" />}>{t("settings.signins.logoutAll")}</Button>
        </Section>
      </div>
    </div>
  );
}
