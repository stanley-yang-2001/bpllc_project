import { Download, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Modal } from "../components/Modal";
import { useToast } from "../components/Toast";
import { Button, ErrorText, inputCls } from "../components/ui";
import { useI18n } from "../i18n/I18nProvider";
import { Label, Section } from "./Section";

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

export function DataSection() {
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
