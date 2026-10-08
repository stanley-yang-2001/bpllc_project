import { useQuery } from "@tanstack/react-query";
import { Download, LogOut, Monitor, Moon, RefreshCw, Sun, Trash2 } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, type Health } from "../api/client";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { useAuth } from "../auth/AuthContext";
import { Modal } from "../components/Modal";
import { useToast } from "../components/Toast";
import { Badge, Button, Card, ErrorText, inputCls, PageHeader, Skeleton } from "../components/ui";
import { useTheme, type Theme } from "../theme/ThemeProvider";

const msg = (e: unknown) => (e instanceof ApiError ? e.message : "Something went wrong.");

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
      toast("Profile saved");
    } catch (err) { setError(msg(err)); } finally { setBusy(false); }
  };
  return (
    <Section title="Profile" description="Your name is shown in the app. Your native language is the language your word meanings are written in.">
      <form onSubmit={save} className="grid gap-4 sm:grid-cols-2" aria-label="Profile">
        <div>
          <Label htmlFor="p-name">Your name</Label>
          <input id="p-name" className={inputCls} value={name} maxLength={40} onChange={(e) => setName(e.target.value)} autoComplete="name" />
        </div>
        <div>
          <Label htmlFor="p-native">Native language</Label>
          <select id="p-native" className={inputCls} value={native} onChange={(e) => setNative(e.target.value)}>
            {all.map((l) => <option key={l.code} value={l.code}>{l.name}</option>)}
          </select>
        </div>
        <div className="sm:col-span-2">
          <Button type="submit" loading={busy} disabled={!dirty || !name.trim()}>Save profile</Button>
          <ErrorText>{error}</ErrorText>
        </div>
      </form>
    </Section>
  );
}

function EmailSection() {
  const { user, setUser } = useAuth();
  const toast = useToast();
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
      toast("Email address changed");
    } catch (err) { setError(msg(err)); } finally { setBusy(false); }
  };
  return (
    <Section title="Email address" description="You sign in with your email. We don't send you email, so changing it takes effect immediately.">
      <p className="mb-4 text-sm text-slate-600">Current address: <strong className="text-slate-900">{user?.email}</strong></p>
      <form onSubmit={save} className="grid gap-4 sm:grid-cols-2" aria-label="Change email">
        <div>
          <Label htmlFor="e-new">New email</Label>
          <input id="e-new" type="email" autoComplete="email" className={inputCls} value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="e-pass">Current password</Label>
          <input id="e-pass" type="password" autoComplete="current-password" className={inputCls} value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <div className="sm:col-span-2">
          <Button type="submit" variant="secondary" loading={busy} disabled={!email || !password}>Change email</Button>
          <ErrorText>{error}</ErrorText>
        </div>
      </form>
    </Section>
  );
}

function PasswordSection() {
  const toast = useToast();
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
      toast("Password changed. Your other devices were logged out.");
    } catch (err) { setError(msg(err)); } finally { setBusy(false); }
  };
  return (
    <Section title="Password" description="Changing it logs you out of every other browser and device.">
      <form onSubmit={save} className="grid gap-4 sm:grid-cols-3" aria-label="Change password">
        <div>
          <Label htmlFor="pw-cur">Current password</Label>
          <input id="pw-cur" type="password" autoComplete="current-password" className={inputCls} value={current} onChange={(e) => setCurrent(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="pw-new">New password</Label>
          <input id="pw-new" type="password" autoComplete="new-password" className={inputCls} value={next} onChange={(e) => setNext(e.target.value)} />
          <p className="mt-1 text-xs text-slate-500">At least 8 characters.</p>
        </div>
        <div>
          <Label htmlFor="pw-again">New password again</Label>
          <input id="pw-again" type="password" autoComplete="new-password" className={inputCls} value={again} onChange={(e) => setAgain(e.target.value)} />
          <ErrorText>{mismatch ? "The two new passwords don't match" : undefined}</ErrorText>
        </div>
        <div className="sm:col-span-3">
          <Button type="submit" variant="secondary" loading={busy} disabled={!current || next.length < 8 || next !== again}>Change password</Button>
          <ErrorText>{error}</ErrorText>
        </div>
      </form>
    </Section>
  );
}

const themes: { value: Theme; label: string; icon: typeof Sun }[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
];

function AppearanceSection() {
  const { theme, setTheme } = useTheme();
  return (
    <Section title="Appearance" description="“System” follows your device's light or dark setting. This choice is remembered in this browser only.">
      <div role="radiogroup" aria-label="Theme" className="inline-grid grid-cols-3 gap-1 rounded-lg bg-slate-100 p-1">
        {themes.map(({ value, label, icon: Icon }) => (
          <label
            key={value}
            className={`flex cursor-pointer items-center gap-2 rounded-md px-3.5 py-1.5 text-sm transition has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-brand-500 ${
              theme === value ? "bg-surface font-medium text-slate-900 shadow-xs" : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <input type="radio" name="theme" value={value} checked={theme === value} onChange={() => setTheme(value)} className="sr-only" />
            <Icon aria-hidden className="size-4" />
            {label}
          </label>
        ))}
      </div>
    </Section>
  );
}

function DeleteAccountModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { deleteAccount } = useAuth();
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const close = () => { setPassword(""); setError(undefined); onClose(); };
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(undefined);
    try {
      await deleteAccount(password);          // on success the whole screen is cleared and you land on the login page
    } catch (err) { setError(msg(err)); setBusy(false); }
  };
  return (
    <Modal open={open} onClose={close} title="Delete your account?">
      <form onSubmit={submit}>
        <p className="text-sm text-slate-600">This permanently deletes, right now and with no way back:</p>
        <ul className="mt-2 list-disc space-y-0.5 pl-5 text-sm text-slate-600">
          <li>your name and email address</li>
          <li>all your words, meanings and languages</li>
          <li>all your sign-ins, on every device</li>
        </ul>
        <p className="mt-3 text-sm text-slate-600">Consider downloading your data first.</p>
        <div className="mt-4">
          <Label htmlFor="del-pass">Enter your password to confirm</Label>
          <input id="del-pass" type="password" autoComplete="current-password" className={inputCls} value={password} onChange={(e) => setPassword(e.target.value)} data-autofocus />
          <ErrorText>{error}</ErrorText>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={close}>Cancel</Button>
          <Button type="submit" variant="danger" loading={busy} disabled={!password} icon={<Trash2 aria-hidden className="size-4" />}>Delete my account</Button>
        </div>
      </form>
    </Modal>
  );
}

function DataSection() {
  const toast = useToast();
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
      toast("Your data was downloaded");
    } catch (err) { setError(msg(err)); } finally { setBusy(false); }
  };
  return (
    <Section title="Data & privacy" description="You are in control of what we hold about you.">
      <p className="mb-4 text-sm text-slate-600">
        We keep your name, your email and the words you add, and nothing else about you. See the{" "}
        <Link to="/privacy" className="font-medium text-brand-600 underline underline-offset-2 dark:text-brand-200">Privacy Policy</Link>.
      </p>
      <div className="flex flex-wrap gap-3">
        <Button variant="secondary" onClick={() => void download()} loading={busy} icon={<Download aria-hidden className="size-4" />}>Download my data</Button>
        <Button variant="danger" onClick={() => setConfirmOpen(true)} icon={<Trash2 aria-hidden className="size-4" />}>Delete account</Button>
      </div>
      <ErrorText>{error}</ErrorText>
      <DeleteAccountModal open={confirmOpen} onClose={() => setConfirmOpen(false)} />
    </Section>
  );
}

function Row({ label, check }: { label: string; check: Health["postgres"] }) {
  const state = check.ok === true ? "OK" : check.ok === false ? `Problem${check.detail ? ` (${check.detail})` : ""}` : "Not checked yet";
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
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, staleTime: 0 });
  return (
    <div>
      <PageHeader title="Settings" description="Your account, how the app looks, your data, and the services behind it." />
      <div className="space-y-6">
        <Card>
          <h2 className="mb-3 font-semibold text-slate-900">Account</h2>
          <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-[8rem_1fr]">
            <dt className="text-slate-500">Email</dt>
            <dd className="font-medium text-slate-900">{user?.email}</dd>
            <dt className="text-slate-500">Languages</dt>
            <dd className="flex flex-wrap gap-1.5">{user?.languages.map((l) => <Badge key={l} tone="brand">{l.toUpperCase()}</Badge>)}</dd>
          </dl>
        </Card>
        <ProfileSection />
        <EmailSection />
        <PasswordSection />
        <AppearanceSection />
        <DataSection />

        <Card>
          <div className="mb-2 flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">Services</h2>
            <Button variant="secondary" onClick={() => void health.refetch()} loading={health.isFetching} icon={<RefreshCw aria-hidden className="size-4" />}>Re-check</Button>
          </div>
          {health.isPending ? (
            <div className="space-y-3 py-2"><Skeleton className="h-5 w-full" /><Skeleton className="h-5 w-full" /><Skeleton className="h-5 w-full" /></div>
          ) : health.isError ? (
            <ErrorText>{msg(health.error)}</ErrorText>
          ) : (
            <ul>
              <Row label="Postgres" check={health.data.postgres} />
              <Row label="Langflow (chat)" check={{ ok: null }} />
              <Row label="Groq (stories)" check={{ ok: null }} />
            </ul>
          )}
        </Card>

        <Section title="Sign-ins" description="Ends your login on every browser and device, including this one. Use it on a shared or lost computer.">
          <Button variant="secondary" onClick={() => void logoutAll()} icon={<LogOut aria-hidden className="size-4" />}>Log out everywhere</Button>
        </Section>
      </div>
    </div>
  );
}
