import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Plus, Search, SearchX, Sparkles, Type, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { setsKey, wordsKey } from "../api/keys";
import { api, type SetFilter, type UploadResult } from "../api/client";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { useAuth } from "../auth/AuthContext";
import { KindBadge, MAX_LINES, usePronunciation } from "../text/PronunciationLines";
import { TranslateBox } from "../text/TranslateBox";
import { useI18n } from "../i18n/I18nProvider";
import { Button, Card, EmptyState, ErrorText, inputCls, PageHeader, Skeleton } from "../components/ui";
import { AddWordForm } from "../vocab/AddWordForm";
import { BulkBar } from "../vocab/BulkBar";
import { defineLoop } from "../vocab/defineLoop";
import { Pager } from "../vocab/Pager";
import { SetBar } from "../vocab/SetBar";
import { UploadNotice } from "../vocab/UploadNotice";
import { useBulkActions } from "../vocab/useBulkActions";
import { useDebounced } from "../vocab/useDebounced";
import { WordTable } from "../vocab/WordTable";
import { useToast } from "../components/Toast";
import { usePreferences } from "../prefs/PreferencesProvider";
import { MeaningLanguage } from "../vocab/MeaningLanguage";

const LIMIT = 50;

/** The vocabulary page: it holds the state (search, page, ticks, set filter) and lays out the pieces in `../vocab/`. */
export default function Vocabulary() {
  const qc = useQueryClient();
  const toast = useToast();
  const { t, err } = useI18n();
  const { prefs } = usePreferences();
  const { user, setUser } = useAuth();
  const { active, setActive, all, info } = useActiveLanguage();
  const [search, setSearch] = useState("");
  const q = useDebounced(search, 300);
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [upload, setUpload] = useState<UploadResult | null>(null);
  const [newLang, setNewLang] = useState("");
  const [setFilter, setSetFilter] = useState<SetFilter>("all");
  const [showReading, setShowReading] = useState(false);
  const [translating, setTranslating] = useState(false);
  const [progress, setProgress] = useState<{ done: number; left: number } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => { setSetFilter("all"); }, [active]);
  useEffect(() => { setOffset(0); setSelected(new Set()); setUpload(null); }, [active, q, setFilter]);

  const setList = useQuery({ queryKey: setsKey(user!.id, active), queryFn: () => api.sets(active) });
  const sets = setList.data?.items ?? [];
  const setNames = new Map<number, string>(sets.map((x) => [x.id, x.name]));
  const refreshSets = () => void qc.invalidateQueries({ queryKey: setsKey(user!.id, active) });

  const words = useQuery({
    queryKey: wordsKey(user!.id, active, q, offset, String(setFilter)),
    queryFn: () => api.words({ language: active, q, limit: LIMIT, offset, set: setFilter }),
    placeholderData: keepPreviousData,
  });

  const { remove, move } = useBulkActions(active, () => setSelected(new Set()), refreshSets);

  const csv = useMutation({
    mutationFn: (file: File) => api.uploadWords(active, file),
    onSuccess: (r) => { setUpload(r); refreshSets(); void qc.invalidateQueries({ queryKey: wordsKey(user!.id, active) }); },
    onSettled: () => { if (fileRef.current) fileRef.current.value = ""; },
  });

  const define = useMutation({
    mutationFn: () => defineLoop({ language: active, set: setFilter, meaning_mode: prefs.meaning_mode }, (done, left) => setProgress({ done, left })),
    onSuccess: (r) => {
      toast(r.done === 0 && r.failed === 0 ? t("vocab.defineNone") : t("vocab.defineDone", { count: r.done }));
      void qc.invalidateQueries({ queryKey: wordsKey(user!.id, active) });
    },
    onSettled: () => setProgress(null),
  });

  const addLang = useMutation({
    mutationFn: (code: string) => api.addLanguage(code),
    onSuccess: (u, code) => { setUser(u); setActive(code); setNewLang(""); },
  });

  const items = words.data?.items ?? [];
  const reading = usePronunciation(active, items.map((w) => w.word), showReading);
  const readings = new Map((reading.data?.items ?? []).map((r) => [r.text, r.reading]));
  const pickedWords = items.filter((w) => selected.has(w.id)).map((w) => w.word);
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

      <AddWordForm language={active} languageName={langName} sets={sets} filter={setFilter} onChanged={refreshSets} />

      <Card className="p-0">
        <SetBar language={active} filter={setFilter} onFilter={setSetFilter} />
        <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 p-4">
          <div className="relative min-w-52 max-w-xs flex-1">
            <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-500" />
            <input aria-label={t("vocab.searchAria")} placeholder={t("vocab.searchPlaceholder")} value={search} onChange={(e) => setSearch(e.target.value)} className={`${inputCls} pl-9`} />
          </div>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <Button variant="secondary" aria-pressed={showReading} loading={reading.isFetching && showReading} icon={<Type aria-hidden className="size-4" />} onClick={() => setShowReading(!showReading)}>{showReading ? t("reading.hide") : t("reading.show")}</Button>
            <MeaningLanguage />
            <Button variant="secondary" loading={define.isPending} icon={<Sparkles aria-hidden className="size-4" />} onClick={() => define.mutate()}>{t("vocab.defineMissing")}</Button>
            <input ref={fileRef} type="file" accept=".csv,text/csv" hidden aria-label={t("vocab.csvFile")} onChange={(e) => { const f = e.target.files?.[0]; if (f) csv.mutate(f); }} />
            <Button variant="secondary" loading={csv.isPending} icon={<Upload aria-hidden className="size-4" />} onClick={() => fileRef.current?.click()}>{t("vocab.uploadCsv")}</Button>
          </div>
        </div>

        {(progress || define.error || move.error) && (
          <div className="space-y-1 border-b border-slate-200 px-4 py-2">
            {progress && <p role="status" className="text-sm text-slate-700">{t("vocab.defining", { done: progress.done, left: progress.left })}</p>}
            <ErrorText>{define.error ? err(define.error) : move.error ? err(move.error) : undefined}</ErrorText>
          </div>
        )}
        {selected.size > 0 && (
          <BulkBar count={selected.size} sets={sets} moving={move.isPending} translating={translating}
            onMove={(to) => move.mutate({ ids: [...selected], to })}
            onToggleTranslate={() => setTranslating(!translating)}
            onClear={() => setSelected(new Set())}
            onDelete={() => remove.mutate([...selected])} />
        )}

        {selected.size > 0 && translating && (
          <div className="border-b border-slate-200 p-4">
            {pickedWords.length > MAX_LINES ? <ErrorText>{t("translate.tooMany")}</ErrorText>
              : <TranslateBox language={active} texts={pickedWords} words idPrefix="vocab-translate" />}
          </div>
        )}
        {showReading && reading.data && (
          <p className="flex flex-wrap items-center gap-2 border-b border-slate-200 px-4 py-2 text-xs text-slate-600"><KindBadge kind={reading.data.kind} />{reading.data.approximate && t("reading.approx")}</p>
        )}
        {showReading && reading.isError && <div className="border-b border-slate-200 px-4"><ErrorText>{err(reading.error)}</ErrorText></div>}
        {(csv.error || remove.error || upload) && (
          <div className="space-y-2 border-b border-slate-200 p-4">
            <ErrorText>{csv.error ? err(csv.error) : undefined}</ErrorText>
            <ErrorText>{remove.error ? err(remove.error) : undefined}</ErrorText>
            {upload && <UploadNotice result={upload} />}
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
          <WordTable words={items} language={active} selected={selected} onToggle={toggle}
            onToggleAll={() => setSelected(allOnPage ? new Set() : new Set(items.map((w) => w.id)))}
            readings={readings} showReadings={showReading} setNames={sets.length > 0 ? setNames : null} />
        )}

        <Pager offset={offset} limit={LIMIT} total={total} onOffset={setOffset} />
      </Card>
    </div>
  );
}
