import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, type StoryCard } from "../api/client";
import { storiesKey } from "../api/keys";
import { useAuth } from "../auth/AuthContext";
import { useConfirm } from "../components/Confirm";
import { useToast } from "../components/Toast";
import { useI18n } from "../i18n/I18nProvider";

export const LIMIT = 10;

/** The saved stories of one language: the current page, which story is open, and deleting one (after asking). */
export function useLibrary(language: string) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const toast = useToast();
  const { t } = useI18n();
  // The page position belongs to one language, so it is derived rather than reset in an effect: an effect would let one
  // request go out for the new language at the old language's offset.
  const [place, setPlace] = useState({ language, offset: 0 });
  const offset = place.language === language ? place.offset : 0;
  const setOffset = (n: number) => setPlace({ language, offset: n });
  const [openId, setOpenId] = useState<number | null>(null);
  useEffect(() => { setOpenId(null); }, [language]);

  const list = useQuery({
    queryKey: storiesKey(user!.id, "list", language, offset),
    queryFn: () => api.stories({ language, limit: LIMIT, offset }),
    placeholderData: keepPreviousData,
  });
  const remove = useMutation({
    mutationFn: api.deleteStory,
    onSuccess: (_, id) => {
      if (openId === id) setOpenId(null);
      toast(t("library.deleted"));
      void qc.invalidateQueries({ queryKey: storiesKey(user!.id) });
    },
  });
  useEffect(() => { if (list.data && list.data.items.length === 0 && offset > 0) setOffset(Math.max(0, offset - LIMIT)); }, [list.data, offset]);   // the last story on a page was deleted

  const ask = async (s: StoryCard) => {
    if (await confirm({ title: t("library.deleteTitle"), body: t("library.deleteBody"), confirmLabel: t("library.deleteConfirm") })) remove.mutate(s.id);
  };
  return { list, total: list.data?.total ?? 0, offset, setOffset, openId, toggle: (id: number) => setOpenId(openId === id ? null : id), remove, ask };
}
