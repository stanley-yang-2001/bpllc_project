import { useI18n } from "../i18n/I18nProvider";
import { diffLabel, topicLabel, typeLabel } from "../i18n/labels";
import { Badge } from "./ui";

/** The badges that describe a story: its kind, its topic and the difficulty it was asked for. One place, so Studio and Library word them alike. */
export function StoryMeta({ kind, topic, difficulty }: { kind: string | null | undefined; topic?: string | null; difficulty?: string | null }) {
  const { t } = useI18n();
  return (
    <>
      <Badge>{kind ? typeLabel(t, kind) : t("library.fromChat")}</Badge>
      {topic && <Badge>{topicLabel(t, topic)}</Badge>}
      {difficulty && <Badge>{diffLabel(t, difficulty)}</Badge>}
    </>
  );
}
