import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n/I18nProvider";
import type { MessageKey } from "../i18n/messages";
import { chunks } from "../speech/speak";
import { ErrorText, Skeleton } from "../components/ui";

export const MAX_LINES = 60;

/** The readings for some texts (one request, cached for the session; nothing is stored on the server). */
export function usePronunciation(language: string, texts: string[], enabled: boolean) {
  const { user } = useAuth();
  const list = texts.slice(0, MAX_LINES);
  return useQuery({
    queryKey: ["pronounce", user!.id, language, list],
    queryFn: () => api.pronounce({ language, texts: list }),
    enabled: enabled && list.length > 0,
    staleTime: Infinity,
    gcTime: 10 * 60 * 1000,
    retry: false,
  });
}

/** The label of a reading kind: IPA, Pinyin, Romaji or Romanization. */
export function KindBadge({ kind }: { kind: string }) {
  const { t } = useI18n();
  return <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-700">{t(`reading.kind.${kind}` as MessageKey)}</span>;
}

/** A story (or any text) split into sentences, each with its reading underneath. */
export function PronunciationLines({ text, language }: { text: string; language: string }) {
  const { t, err } = useI18n();
  const lines = chunks(text).slice(0, MAX_LINES);
  const q = usePronunciation(language, lines, true);
  if (q.isPending) return <Skeleton className="h-16 w-full" />;
  if (q.isError) return <ErrorText>{err(q.error)}</ErrorText>;
  return (
    <div className="space-y-2 rounded-lg border border-slate-200 p-3" aria-label={t("reading.show")}>
      <p className="flex flex-wrap items-center gap-2 text-xs text-slate-600"><KindBadge kind={q.data.kind} />{q.data.approximate && t("reading.approx")}</p>
      {q.data.items.map((item, i) => (
        <p key={i} className="text-sm">
          <span lang={language} className="block text-slate-900">{item.text}</span>
          <span className="block text-slate-600">{item.reading ?? t("reading.none")}</span>
        </p>
      ))}
    </div>
  );
}
