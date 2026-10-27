import { useQuery } from "@tanstack/react-query";
import { RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type ClozeItem } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n/I18nProvider";
import { Button, ErrorText, Skeleton } from "../components/ui";

/** Fill in the blank in a saved story, one word at a time. Nothing is stored. */
export function Blanks({ storyId, onDone }: { storyId: number; onDone: () => void }) {
  const { user } = useAuth();
  const { t, err } = useI18n();
  const set = useQuery({ queryKey: ["practice", user!.id, "cloze", storyId], queryFn: () => api.cloze(storyId), gcTime: 0, staleTime: Infinity });
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [right, setRight] = useState(0);
  useEffect(() => { setIndex(0); setPicked(null); setRight(0); }, [storyId]);

  if (set.isPending) return <Skeleton className="h-40 w-full" />;
  if (set.isError) return <ErrorText>{err(set.error)}</ErrorText>;
  const items: ClozeItem[] = set.data.items;
  if (index >= items.length)
    return (
      <div className="space-y-3 text-center" role="status">
        <p className="text-lg font-semibold text-slate-900">{t("practice.cloze.score", { right, total: items.length })}</p>
        <div className="flex justify-center gap-2">
          <Button onClick={() => { setIndex(0); setPicked(null); setRight(0); }} icon={<RotateCcw aria-hidden className="size-4" />}>{t("common.tryAgain")}</Button>
          <Button variant="secondary" onClick={onDone}>{t("common.back")}</Button>
        </div>
      </div>
    );
  const item = items[index];
  const choose = (choice: string) => {
    if (picked !== null) return;
    setPicked(choice);
    if (choice === item.answer) setRight(right + 1);
  };
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">{t("practice.cloze.sentenceOf", { n: index + 1, total: items.length })}</p>
      <p lang={set.data.language} className="text-lg leading-relaxed text-slate-900">
        {item.before}<span className="mx-1 inline-block min-w-16 border-b-2 border-slate-400 text-center font-semibold">{picked !== null ? item.answer : " "}</span>{item.after}
      </p>
      {item.hint && <p className="text-sm text-slate-600">{t("practice.cloze.hint", { hint: item.hint })}</p>}
      <div className="flex flex-wrap gap-2" role="group" aria-label={t("practice.cloze.choices")}>
        {item.choices.map((c) => (
          <Button key={c} variant="secondary" onClick={() => choose(c)} disabled={picked !== null && c !== picked && c !== item.answer} lang={set.data.language}>{c}</Button>
        ))}
      </div>
      {picked !== null && (
        <div className="space-y-2" role="status">
          <p className={picked === item.answer ? "font-medium text-emerald-700 dark:text-emerald-400" : "font-medium text-red-700 dark:text-red-400"}>
            {picked === item.answer ? t("practice.cloze.correct") : t("practice.cloze.wrong", { answer: item.answer })}
          </p>
          <Button onClick={() => { setPicked(null); setIndex(index + 1); }}>{index + 1 === items.length ? t("practice.cloze.seeResult") : t("common.next")}</Button>
        </div>
      )}
    </div>
  );
}
