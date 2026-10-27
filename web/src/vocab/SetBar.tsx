import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { setsKey, wordsKey } from "../api/keys";
import { api, type SetFilter, type WordSet } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useConfirm } from "../components/Confirm";
import { useToast } from "../components/Toast";
import { useI18n } from "../i18n/I18nProvider";
import { Button, ErrorText, inputCls } from "../components/ui";

/** The tabs (All, General, one per set) and the controls to make, rename and delete sets. General cannot be renamed or deleted. */
export function SetBar({ language, filter, onFilter }: { language: string; filter: SetFilter; onFilter: (f: SetFilter) => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();
  const { user } = useAuth();
  const { t, err } = useI18n();
  const sets = useQuery({ queryKey: setsKey(user!.id, language), queryFn: () => api.sets(language) });
  const [name, setName] = useState("");
  const [renaming, setRenaming] = useState<string | null>(null);
  const refresh = () => { void qc.invalidateQueries({ queryKey: setsKey(user!.id, language) }); void qc.invalidateQueries({ queryKey: wordsKey(user!.id, language) }); };
  const create = useMutation({
    mutationFn: (n: string) => api.createSet({ language, name: n }),
    onSuccess: (s) => { setName(""); toast(t("sets.created", { name: s.name })); onFilter(s.id); refresh(); },
  });
  const rename = useMutation({
    mutationFn: (v: { id: number; name: string }) => api.renameSet(v.id, v.name),
    onSuccess: () => { setRenaming(null); refresh(); },
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.deleteSet(id),
    onSuccess: () => { toast(t("sets.deleted")); onFilter("all"); refresh(); },
  });
  const items: WordSet[] = sets.data?.items ?? [];
  const current = typeof filter === "number" ? items.find((s) => s.id === filter) : undefined;
  const tab = (key: string, label: string, count: number | undefined, on: boolean, go: () => void) => (
    <button key={key} type="button" aria-pressed={on} onClick={go}
      className={`rounded-full border px-3 py-1 text-sm ${on ? "border-brand-600 bg-brand-600 text-white" : "border-slate-300 bg-surface text-slate-700 hover:bg-slate-100/70"}`}>
      {label}{count !== undefined && <span className="ml-1 opacity-80">({count})</span>}
    </button>
  );
  return (
    <div className="space-y-3 border-b border-slate-200 p-4" role="group" aria-label={t("sets.filterAria")}>
      <div className="flex flex-wrap items-center gap-2">
        {tab("all", t("sets.all"), sets.data?.total_count, filter === "all", () => onFilter("all"))}
        {tab("general", t("sets.general"), sets.data?.general_count, filter === "general", () => onFilter("general"))}
        {items.map((s) => tab(String(s.id), s.name, s.count, filter === s.id, () => onFilter(s.id)))}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <input aria-label={t("sets.newName")} placeholder={t("sets.newName")} maxLength={40} className={`${inputCls} w-52`} value={name} onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && name.trim()) create.mutate(name); }} />
        <Button variant="secondary" disabled={!name.trim()} loading={create.isPending} icon={<Plus aria-hidden className="size-4" />} onClick={() => create.mutate(name)}>{t("sets.create")}</Button>
        {current && renaming === null && (
          <>
            <Button variant="ghost" icon={<Pencil aria-hidden className="size-4" />} onClick={() => setRenaming(current.name)}>{t("sets.rename")}</Button>
            <Button variant="ghost" icon={<Trash2 aria-hidden className="size-4" />}
              onClick={async () => {
                if (await confirm({ title: t("sets.deleteTitle", { name: current.name }), body: t("sets.deleteBody"), confirmLabel: t("sets.deleteConfirm") })) remove.mutate(current.id);
              }}>{t("sets.delete")}</Button>
          </>
        )}
        {current && renaming !== null && (
          <>
            <input aria-label={t("sets.renameAria", { name: current.name })} autoFocus maxLength={40} className={`${inputCls} w-52`} value={renaming} onChange={(e) => setRenaming(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && renaming.trim()) rename.mutate({ id: current.id, name: renaming }); if (e.key === "Escape") setRenaming(null); }} />
            <Button disabled={!renaming.trim()} loading={rename.isPending} onClick={() => rename.mutate({ id: current.id, name: renaming })}>{t("sets.save")}</Button>
            <Button variant="ghost" onClick={() => setRenaming(null)}>{t("common.cancel")}</Button>
          </>
        )}
      </div>
      <p className="text-xs text-slate-600">{t("sets.limit")}</p>
      <ErrorText>{create.error ? err(create.error) : rename.error ? err(rename.error) : remove.error ? err(remove.error) : undefined}</ErrorText>
    </div>
  );
}
