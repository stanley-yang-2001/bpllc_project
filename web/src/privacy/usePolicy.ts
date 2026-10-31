import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { useI18n } from "../i18n/I18nProvider";
import type { PolicyDoc } from "./types";

/** The policy in the learner's interface language, unless they picked another from the offered ones. */
export function usePolicy() {
  const { locale } = useI18n();
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: Infinity });
  const languages = useQuery({ queryKey: ["languages"], queryFn: api.languages, staleTime: Infinity });
  const [picked, setPicked] = useState<string | null>(null);
  const wanted = picked ?? locale;
  const policy = useQuery({ queryKey: ["policy", wanted], queryFn: () => api.policy(wanted), staleTime: Infinity, enabled: meta.isSuccess || meta.isError });
  return {
    offered: meta.data?.policy_languages ?? ["en"],
    contact: meta.data?.privacy_contact,
    shown: policy.data?.language ?? wanted,
    setPicked,
    nameOf: (code: string) => languages.data?.find((l) => l.code === code)?.native ?? code,
    data: policy.data,
    doc: policy.data?.doc as unknown as PolicyDoc | undefined,
  };
}
