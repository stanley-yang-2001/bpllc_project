import { useState } from "react";
import { api } from "../api/client";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { Button, ErrorText, inputCls } from "../components/ui";
import { useI18n } from "../i18n/I18nProvider";
import { Label, Section } from "./Section";

export function ProfileSection() {
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

export function EmailSection() {
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

export function PasswordSection() {
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
