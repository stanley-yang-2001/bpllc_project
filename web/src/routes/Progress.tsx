import { Link } from "react-router-dom";
import { useI18n } from "../i18n/I18nProvider";
import { Card, ErrorText, PageHeader, Skeleton } from "../components/ui";
import { BadgeGrid } from "../rewards/BadgeGrid";
import { RecordsCard } from "../rewards/RecordsCard";
import { RewardsCard } from "../rewards/RewardsCard";
import { StoryWordsCard } from "../rewards/StoryWordsCard";
import { useRewards } from "../rewards/useRewards";

/** The progress page: the same card as Home, then every badge. */
export default function Progress() {
  const { t } = useI18n();
  const q = useRewards();
  return (
    <div>
      <PageHeader title={t("rewards.title")} description={t("rewards.page.description")} />
      {q.isError ? <ErrorText>{t("error.generic")}</ErrorText>
        : !q.data ? <Skeleton className="h-40 w-full" />
        : !q.data.show_rewards ? <Card><p className="text-sm text-slate-700">{t("rewards.hidden")} <Link to="/settings" className="font-medium text-brand-700 hover:underline dark:text-brand-200">{t("nav.settings")}</Link></p></Card>
        : (
          <>
            <RewardsCard />
            <RecordsCard records={q.data.records} />
            <StoryWordsCard used={q.data.story_words.used} total={q.data.story_words.total} />
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">{t("rewards.badges.title")}</h2>
            <BadgeGrid badges={q.data.badges} />
          </>
        )}
    </div>
  );
}
