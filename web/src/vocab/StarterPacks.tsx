import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, PackagePlus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type StarterAdded } from "../api/client";
import { starterKey, wordsKey } from "../api/keys";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n/I18nProvider";
import type { MessageKey } from "../i18n/messages";
import { Button, Card, ErrorText, Skeleton } from "../components/ui";

const TITLES: Record<string, MessageKey> = {
  basics: "starter.pack.basics", food: "starter.pack.food", people: "starter.pack.people", numbers: "starter.pack.numbers",
};

/** One-click packs of everyday words for the language being studied. Words already in the list are never touched. For a learner who
 * reads English the words come with a short English meaning; for anyone else they have none yet and the tutor writes them. */
export function StarterPacks({ language, onAdded, linkToVocabulary = false }: { language: string; onAdded?: () => void; linkToVocabulary?: boolean }) {
  const { user } = useAuth();
  const { t, err } = useI18n();
  const qc = useQueryClient();
  const packs = useQuery({ queryKey: starterKey(user!.id, language), queryFn: () => api.starterPacks(language) });
  const [done, setDone] = useState<StarterAdded | null>(null);
  const add = useMutation({
    mutationFn: (pack: string) => api.addStarterPack({ language, pack }),
    onSuccess: (r) => {
      setDone(r);
      void qc.invalidateQueries({ queryKey: wordsKey(user!.id, language) });
      void qc.invalidateQueries({ queryKey: starterKey(user!.id, language) });
      void qc.invalidateQueries({ queryKey: ["me"] });
      onAdded?.();
    },
  });
  if (packs.isPending) return <Skeleton className="h-28 w-full" />;
  if (packs.isError || packs.data.items.length === 0) return null;          // a convenience: if it can't load, the page works without it
  return (
    <Card className="space-y-3">
      <div>
        <h2 className="flex items-center gap-2 font-semibold text-slate-900"><PackagePlus aria-hidden className="size-5" />{t("starter.title")}</h2>
        <p className="text-sm text-slate-600">{t("starter.text")}</p>
      </div>
      <ul className="grid gap-2 sm:grid-cols-2">
        {packs.data.items.map((p) => (
          <li key={p.id} className="flex items-center justify-between gap-2 rounded-lg border border-slate-200 px-3 py-2">
            <span className="text-sm font-medium text-slate-900">{TITLES[p.id] ? t(TITLES[p.id]) : p.id}</span>
            {p.remaining === 0
              ? <span className="flex items-center gap-1 text-sm text-slate-600"><Check aria-hidden className="size-4" />{t("starter.complete")}</span>
              : <Button variant="secondary" loading={add.isPending && add.variables === p.id} disabled={add.isPending}
                  aria-label={`${t(TITLES[p.id] ?? "starter.title")}: ${t("starter.add", { n: p.remaining })}`} onClick={() => add.mutate(p.id)}>{t("starter.add", { n: p.remaining })}</Button>}
          </li>
        ))}
      </ul>
      {add.isError && <ErrorText>{err(add.error)}</ErrorText>}
      {done && (
        <p role="status" className="text-sm text-slate-700">
          {done.added === 0 ? t("starter.addedNone") : done.with_meaning ? t("starter.addedWith", { added: done.added }) : t("starter.addedWithout", { added: done.added, button: t("vocab.defineMissing") })}
          {done.added > 0 && !done.with_meaning && linkToVocabulary && <> <Link to="/vocabulary" className="font-medium text-brand-600 underline dark:text-brand-200">{t("starter.goVocabulary")}</Link></>}
        </p>
      )}
    </Card>
  );
}
