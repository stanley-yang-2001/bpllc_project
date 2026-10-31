import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { Badge, Card, Notice, PageHeader } from "../components/ui";
import { useI18n } from "../i18n/I18nProvider";
import { GeneratedStory } from "../studio/GeneratedStory";
import { OptionsForm } from "../studio/OptionsForm";
import { useStoryChoices } from "../studio/useStoryChoices";
import { useStoryGeneration } from "../studio/useStoryGeneration";

export { customLabel } from "../studio/labels";

/** Story Studio: pick a kind, topic and difficulty, make a story from your own words, read its report, save it. The pieces are in studio/. */
export default function Studio() {
  const { active, info } = useActiveLanguage();
  const { t } = useI18n();
  const lang = info(active);
  const name = lang?.native ?? active;
  const options = useQuery({ queryKey: ["story-options"], queryFn: api.storyOptions, staleTime: Infinity });
  const choices = useStoryChoices(active, options.data);
  const g = useStoryGeneration(active, () => choices.setSets(null));
  const make = () => g.generate.mutate(choices.request);
  const enabled = lang?.stories_enabled !== false;

  return (
    <div>
      <PageHeader title={t("studio.title")} description={t("studio.description")} actions={<Badge tone="brand"><span lang={active}>{name}</span></Badge>} />
      <Card className="space-y-4">
        {!enabled ? <Notice tone="warning">{t("studio.unavailable", { language: name })}</Notice>
          : <OptionsForm language={active} options={options.data} c={choices} g={g} onMake={make} />}
      </Card>
      <GeneratedStory g={g} languageName={name} onAnother={make} />
    </div>
  );
}
