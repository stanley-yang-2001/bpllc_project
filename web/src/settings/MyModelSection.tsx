import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useState } from "react";
import { api } from "../api/client";
import { useToast } from "../components/Toast";
import { Button, ErrorText, inputCls } from "../components/ui";
import { useI18n } from "../i18n/I18nProvider";
import { Label, Section } from "./Section";

export function MyModelSection() {
  const { t, err: errText } = useI18n();
  const toast = useToast();
  const qc = useQueryClient();
  const mine = useQuery({ queryKey: ["my-model"], queryFn: api.myModel, staleTime: 0 });
  const saved = mine.data;
  const [model, setModel] = useState<string | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [key, setKey] = useState("");
  const [dropKey, setDropKey] = useState(false);
  const [busy, setBusy] = useState<"" | "test" | "save" | "remove">("");
  const [error, setError] = useState<string>();
  if (!saved?.enabled) return null;                       // the feature is switched on per account by the operator
  const m = model ?? saved.model ?? "";
  const u = url ?? saved.base_url ?? "";
  const body = { model: m.trim(), base_url: u.trim(), ...(key.trim() ? { api_key: key.trim() } : {}), ...(dropKey ? { remove_key: true } : {}) };
  const ready = body.model !== "" && body.base_url !== "";
  const run = async (what: "test" | "save" | "remove") => {
    setBusy(what); setError(undefined);
    try {
      if (what === "test") { await api.testMyModel(body); toast(t("settings.model.tested")); }
      if (what === "save") {
        const next = await api.saveMyModel(body);
        qc.setQueryData(["my-model"], next);
        setModel(null); setUrl(null); setKey(""); setDropKey(false);
        toast(t("settings.model.saved"));
      }
      if (what === "remove") {
        await api.removeMyModel();
        await qc.invalidateQueries({ queryKey: ["my-model"] });
        setModel(null); setUrl(null); setKey(""); setDropKey(false);
        toast(t("settings.model.removed"));
      }
    } catch (e) { setError(errText(e)); } finally { setBusy(""); }
  };
  return (
    <Section title={t("settings.model.title")} description={t("settings.model.description")}>
      <form className="grid gap-4 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); if (ready) void run("save"); }} aria-label={t("settings.model.title")}>
        <div>
          <Label htmlFor="mm-name">{t("settings.model.name")}</Label>
          <input id="mm-name" className={inputCls} value={m} maxLength={100} onChange={(e) => setModel(e.target.value)} placeholder="gpt-4o-mini" autoComplete="off" spellCheck={false} />
        </div>
        <div>
          <Label htmlFor="mm-url">{t("settings.model.address")}</Label>
          <input id="mm-url" className={inputCls} value={u} maxLength={200} onChange={(e) => setUrl(e.target.value)} placeholder="https://api.openai.com/v1" autoComplete="off" spellCheck={false} />
        </div>
        <div className="sm:col-span-2">
          <Label htmlFor="mm-key">{t("settings.model.key")}</Label>
          <input id="mm-key" type="password" className={inputCls} value={key} maxLength={300} onChange={(e) => setKey(e.target.value)} autoComplete="off" aria-describedby="mm-key-hint" />
          <p id="mm-key-hint" className="mt-1 text-xs text-slate-600">
            {saved.has_key && saved.key_last4 ? t("settings.model.keySaved", { last4: saved.key_last4 }) : t("settings.model.keyNone")}
          </p>
          {saved.has_key && (
            <label className="mt-2 flex cursor-pointer items-center gap-2 text-xs text-slate-700">
              <input type="checkbox" className="size-4 rounded accent-brand-600" checked={dropKey} onChange={(e) => setDropKey(e.target.checked)} />
              {t("settings.model.dropKey")}
            </label>
          )}
        </div>
        <div className="flex flex-wrap gap-2 sm:col-span-2">
          <Button type="button" variant="secondary" onClick={() => void run("test")} loading={busy === "test"} disabled={!ready || busy !== ""}>{t("settings.model.test")}</Button>
          <Button type="submit" loading={busy === "save"} disabled={!ready || busy !== ""}>{t("settings.model.save")}</Button>
          {saved.configured && <Button type="button" variant="ghost" onClick={() => void run("remove")} loading={busy === "remove"} disabled={busy !== ""} icon={<Trash2 aria-hidden className="size-4" />}>{t("settings.model.remove")}</Button>}
        </div>
        {error && <div className="sm:col-span-2"><ErrorText>{error}</ErrorText></div>}
      </form>
    </Section>
  );
}
