import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, ChevronLeft, ChevronRight, Pencil, Plus, Search, SearchX, Trash2, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { wordsKey } from "../api/keys";
import { api, type UploadResult, type Word, type WordPage } from "../api/client";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { useAuth } from "../auth/AuthContext";
import { useConfirm } from "../components/Confirm";
import { useToast } from "../components/Toast";
import { useI18n } from "../i18n/I18nProvider";
import { Badge, Button, Card, EmptyState, ErrorText, inputCls, Notice, PageHeader, Skeleton } from "../components/ui";

const LIMIT = 50;

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

function MeaningCell({ word, language }: { word: Word; language: string }) {
  const qc = useQueryClient();
  const { user } = useAuth();
  const { t, err } = useI18n();
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(word.meaning ?? "");
  const save = useMutation({
    mutationFn: (meaning: string | null) => api.editWord(word.id, { meaning }),
    onSuccess: () => { setEditing(false); void qc.invalidateQueries({ queryKey: wordsKey(user!.id, language) }); },
  });
  const commit = () => {
    const next = text.trim() || null;
    if (next === (word.meaning ?? null)) return setEditing(false);
    save.mutate(next);
  };
  if (!editing)
    return (
      <button
        className="group inline-flex items-center gap-1.5 rounded text-left text-slate-700 hover:text-slate-900"
        onClick={() => { setText(word.meaning ?? ""); setEditing(true); }}
        aria-label={t("vocab.editMeaning", { word: word.word })}
      >
        {word.meaning ?? <span className="text-slate-600">{t("vocab.addMeaning")}</span>}
        <Pencil aria-hidden className="size-3.5 text-slate-500 opacity-0 transition group-hover:opacity-100 group-focus-visible:opacity-100" />
      </button>
    );
  return (
    <div>
      <input
        autoFocus
        aria-label={t("vocab.meaningOf", { word: word.word })}
        className={`${inputCls} py-1.5`}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => { if (e.key === "Enter") commit(); if (e.key === "Escape") setEditing(false); }}
      />
      <ErrorText>{save.error ? err(save.error) : undefined}</ErrorText>
    </div>
  );
}

export default function Vocabulary() {
  const qc = useQueryClient();
  const toast = useToast();
  const { t, tc, err } = useI18n();
  const confirm = useConfirm();
  const { user, setUser } = useAuth();
  const { active, setActive, all, info } = useActiveLanguage();
  const [search, setSearch] = useState("");
  const q = useDebounced(search, 300);
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [upload, setUpload] = useState<UploadResult | null>(null);
  const [newLang, setNewLang] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => { setOffset(0); setSelected(new Set()); setUpload(null); }, [active, q]);

  const words = useQuery({
    queryKey: wordsKey(user!.id, active, q, offset),
    queryFn: () => api.words({ language: active, q, limit: LIMIT, offset }),
    placeholderData: keepPreviousData,
  });

  const form = useForm<{ word: string; meaning: string }>({ defaultValues: { word: "", meaning: "" } });
  const add = useMutation({
    // not optimistic: the server normalises the word and may reject it as a duplicate
    mutationFn: (v: { word: string; meaning: string }) => api.addWord({ language: active, word: v.word, meaning: v.meaning || undefined }),
    onSuccess: (w) => {
      form.reset();
      toast(t("vocab.added", { word: w.word }));
      void qc.invalidateQueries({ queryKey: wordsKey(user!.id, active) });
      void qc.invalidateQueries({ queryKey: ["me"] });
    },
  });

  const remove = useMutation({
    mutationFn: (ids: number[]) => api.deleteWords(ids),
    onMutate: async (ids) => {            // optimistic: deleting can't be rejected by normalisation
      await qc.cancelQueries({ queryKey: wordsKey(user!.id, active) });
      const snapshot = qc.getQueriesData<WordPage>({ queryKey: wordsKey(user!.id, active) });
      qc.setQueriesData<WordPage>({ queryKey: wordsKey(user!.id, active) }, (p) =>
        p ? { ...p, items: p.items.filter((w) => !ids.includes(w.id)), total: Math.max(0, p.total - ids.length) } : p);
      setSelected(new Set());
      return { snapshot };
    },
    onSuccess: (r) => toast(tc("vocab.deleted", r.deleted)),
    onError: (_e, _ids, ctx) => ctx?.snapshot.forEach(([key, data]) => qc.setQueryData(key, data)),
    onSettled: () => void qc.invalidateQueries({ queryKey: wordsKey(user!.id, active) }),
  });

  const csv = useMutation({
    mutationFn: (file: File) => api.uploadWords(active, file),
    onSuccess: (r) => { setUpload(r); void qc.invalidateQueries({ queryKey: wordsKey(user!.id, active) }); },
    onSettled: () => { if (fileRef.current) fileRef.current.value = ""; },
  });

  const addLang = useMutation({
    mutationFn: (code: string) => api.addLanguage(code),
    onSuccess: (u, code) => { setUser(u); setActive(code); setNewLang(""); },
  });

  const items = words.data?.items ?? [];
  const total = words.data?.total ?? 0;
  const langName = info(active)?.native ?? active;
  const toggle = (id: number) => setSelected((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const allOnPage = items.length > 0 && items.every((w) => selected.has(w.id));
  const others = all.filter((l) => !user?.languages.includes(l.code));

  return (
    <div>
      <PageHeader
        title={<>{t("nav.vocabulary")} — <span lang={active}>{langName}</span> <span className="text-lg font-normal text-slate-500">({total})</span></>}
        description={t("vocab.description")}
        actions={others.length > 0 && (
          <div className="flex items-center gap-2">
            <select aria-label={t("vocab.languageToStart")} value={newLang} onChange={(e) => setNewLang(e.target.value)} className={`${inputCls} w-auto`}>
              <option value="">{t("vocab.studyAnother")}</option>
              {others.map((l) => <option key={l.code} value={l.code} lang={l.code}>{l.native}</option>)}
            </select>
            <Button variant="secondary" disabled={!newLang} loading={addLang.isPending} onClick={() => addLang.mutate(newLang)}>{t("common.add")}</Button>
          </div>
        )}
      />

      <Card className="mb-6">
        <form onSubmit={form.handleSubmit((v) => add.mutate(v))} className="flex flex-wrap items-start gap-3" aria-label={t("vocab.addForm")}>
          <div className="min-w-44 flex-1">
            <input aria-label={t("vocab.word")} placeholder={t("vocab.wordPlaceholder", { language: langName })} className={inputCls} data-word-input {...form.register("word", { required: true })} />
          </div>
          <div className="min-w-44 flex-1">
            <input aria-label={t("vocab.meaningOptional")} placeholder={t("vocab.meaningOptional")} className={inputCls} {...form.register("meaning")} />
          </div>
          <Button type="submit" loading={add.isPending} icon={<Plus aria-hidden className="size-4" />}>{t("vocab.addWord")}</Button>
        </form>
        <ErrorText>{add.error ? err(add.error) : undefined}</ErrorText>
        <p className="mt-3 text-xs text-slate-500">{t("vocab.storedHint")}</p>
      </Card>

      <Card className="p-0">
        <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 p-4">
          <div className="relative min-w-52 max-w-xs flex-1">
            <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-500" />
            <input aria-label={t("vocab.searchAria")} placeholder={t("vocab.searchPlaceholder")} value={search} onChange={(e) => setSearch(e.target.value)} className={`${inputCls} pl-9`} />
          </div>
          <div className="ml-auto">
            <input ref={fileRef} type="file" accept=".csv,text/csv" hidden aria-label={t("vocab.csvFile")} onChange={(e) => { const f = e.target.files?.[0]; if (f) csv.mutate(f); }} />
            <Button variant="secondary" loading={csv.isPending} icon={<Upload aria-hidden className="size-4" />} onClick={() => fileRef.current?.click()}>{t("vocab.uploadCsv")}</Button>
          </div>
        </div>

        {selected.size > 0 && (
          <div className="flex items-center justify-between gap-3 border-b border-brand-200 bg-brand-50 px-4 py-2 text-sm text-brand-900 dark:border-brand-800 dark:bg-brand-900/40 dark:text-brand-100">
            <span>{t("vocab.selected", { count: selected.size })}</span>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setSelected(new Set())}>{t("common.clear")}</Button>
              <Button variant="danger" icon={<Trash2 aria-hidden className="size-4" />}
                onClick={async () => {
                  const n = selected.size;
                  const ok = await confirm({
                    title: n === 1 ? t("vocab.deleteOne.title") : t("vocab.deleteMany.title", { count: n }),
                    body: t("vocab.deleteBody"),
                    confirmLabel: n === 1 ? t("vocab.deleteOne.confirm") : t("vocab.deleteMany.confirm", { count: n }),
                  });
                  if (ok) remove.mutate([...selected]);
                }}>
                {t("vocab.deleteSelected", { count: selected.size })}
              </Button>
            </div>
          </div>
        )}

        {(csv.error || remove.error || upload) && (
          <div className="space-y-2 border-b border-slate-200 p-4">
            <ErrorText>{csv.error ? err(csv.error) : undefined}</ErrorText>
            <ErrorText>{remove.error ? err(remove.error) : undefined}</ErrorText>
            {upload && (
              <Notice tone={upload.invalid_count ? "warning" : "success"} role="status">
                <p>{t("vocab.upload.result", { added: upload.added, duplicates: upload.duplicates, invalid: upload.invalid_count })}</p>
                {upload.invalid.length > 0 && (
                  <ul className="mt-1 list-disc pl-5 text-xs">
                    {upload.invalid.map((r) => <li key={r.row}>{t("vocab.upload.row", { row: r.row, reason: r.reason })}</li>)}
                  </ul>
                )}
              </Notice>
            )}
          </div>
        )}

        {words.isPending ? (
          <div role="status" aria-label={t("vocab.loadingWords")} className="space-y-3 p-4">
            {[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-9 w-full" />)}
          </div>
        ) : words.isError ? (
          <div className="p-4"><ErrorText>{err(words.error)}</ErrorText></div>
        ) : items.length === 0 ? (
          q ? (
            <EmptyState icon={<SearchX aria-hidden className="size-5" />} title={t("vocab.noMatch.title")}>{t("vocab.noMatch.body")}</EmptyState>
          ) : (
            <EmptyState
              icon={<BookOpen aria-hidden className="size-5" />}
              title={t("vocab.empty.title")}
              action={<Button onClick={() => document.querySelector<HTMLInputElement>("input[data-word-input]")?.focus()} icon={<Plus aria-hidden className="size-4" />}>{t("vocab.empty.action")}</Button>}
            >
              {t("vocab.empty.body")}
            </EmptyState>
          )
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <th className="w-12 py-3 pl-4">
                    <input type="checkbox" className="size-4 rounded accent-brand-600" aria-label={t("vocab.selectAll")} checked={allOnPage}
                      onChange={() => setSelected(allOnPage ? new Set() : new Set(items.map((w) => w.id)))} />
                  </th>
                  <th className="py-3 pr-4">{t("vocab.colWord")}</th>
                  <th className="py-3 pr-4">{t("vocab.colMeaning")}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((w) => (
                  <tr key={w.id} className={`border-b border-slate-100 last:border-0 transition-colors hover:bg-slate-100/70 ${selected.has(w.id) ? "bg-brand-50/60 dark:bg-brand-900/30" : ""}`}>
                    <td className="py-2.5 pl-4">
                      <input type="checkbox" className="size-4 rounded accent-brand-600" aria-label={t("vocab.select", { word: w.word })} checked={selected.has(w.id)} onChange={() => toggle(w.id)} />
                    </td>
                    <td className="py-2.5 pr-4 font-medium text-slate-900">{w.word}</td>
                    <td className="py-2.5 pr-4"><MeaningCell word={w} language={active} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {total > LIMIT && (
          <div className="flex items-center justify-between border-t border-slate-200 p-3 text-sm text-slate-600">
            <Button variant="ghost" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMIT))} icon={<ChevronLeft aria-hidden className="size-4" />}>{t("common.previous")}</Button>
            <Badge>{t("common.range", { from: offset + 1, to: Math.min(offset + LIMIT, total), total })}</Badge>
            <Button variant="ghost" disabled={offset + LIMIT >= total} onClick={() => setOffset(offset + LIMIT)}>{t("common.next")}<ChevronRight aria-hidden className="size-4" /></Button>
          </div>
        )}
      </Card>
    </div>
  );
}
