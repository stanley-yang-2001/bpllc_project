import { LoaderCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { useI18n } from "../i18n/I18nProvider";
import { SLOW_AFTER_MS } from "./ChatContext";

/** "Thinking…", which turns into "still working" if the tutor takes a while. */
export function Waiting() {
  const { t } = useI18n();
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    return () => clearTimeout(timer);
  }, []);
  return (
    <p role="status" className="flex items-center gap-2 text-sm text-slate-600">
      <LoaderCircle aria-hidden className="size-4 animate-spin" />
      {slow ? t("chat.slow") : t("chat.thinking")}
    </p>
  );
}
