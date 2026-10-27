import { useQuery } from "@tanstack/react-query";
import { LogOut, RefreshCw } from "lucide-react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Badge, Button, Card, ErrorText, PageHeader, Skeleton } from "../components/ui";
import { useI18n } from "../i18n/I18nProvider";
import { AppearanceSection } from "../settings/AppearanceSection";
import { EmailSection, PasswordSection, ProfileSection } from "../settings/AccountSections";
import { DataSection } from "../settings/DataSection";
import { MyModelSection } from "../settings/MyModelSection";
import { Section } from "../settings/Section";
import { ServiceRow } from "../settings/ServiceRow";
import { SiteLanguageSection } from "../settings/SiteLanguageSection";

/** The settings page: the sections live in `../settings/`, this only puts them in order. */
export default function Settings() {
  const { user, logoutAll } = useAuth();
  const { t, err: errText } = useI18n();
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, staleTime: 0 });
  return (
    <div>
      <PageHeader title={t("nav.settings")} description={t("settings.description")} />
      <div className="space-y-6">
        <Card>
          <h2 className="mb-3 font-semibold text-slate-900">{t("settings.account")}</h2>
          <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-[8rem_1fr]">
            <dt className="text-slate-500">{t("settings.email")}</dt>
            <dd className="font-medium text-slate-900">{user?.email}</dd>
            <dt className="text-slate-500">{t("settings.userId")}</dt>
            <dd className="select-all font-medium text-slate-900" data-testid="user-id">{user?.id}</dd>
            <dt className="text-slate-500">{t("settings.languages")}</dt>
            <dd className="flex flex-wrap gap-1.5">{user?.languages.map((l) => <Badge key={l} tone="brand">{l.toUpperCase()}</Badge>)}</dd>
          </dl>
        </Card>
        <ProfileSection />
        <EmailSection />
        <PasswordSection />
        <AppearanceSection />
        <SiteLanguageSection />
        <MyModelSection />
        <DataSection />

        <Card>
          <div className="mb-2 flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">{t("settings.services.title")}</h2>
            <Button variant="secondary" onClick={() => void health.refetch()} loading={health.isFetching} icon={<RefreshCw aria-hidden className="size-4" />}>{t("settings.services.recheck")}</Button>
          </div>
          {health.isPending ? (
            <div className="space-y-3 py-2"><Skeleton className="h-5 w-full" /><Skeleton className="h-5 w-full" /><Skeleton className="h-5 w-full" /></div>
          ) : health.isError ? (
            <ErrorText>{errText(health.error)}</ErrorText>
          ) : (
            <ul>
              <ServiceRow label="Postgres" check={health.data.postgres} />
              <ServiceRow label={t("settings.services.langflow")} check={health.data.langflow} />
              <ServiceRow label={t("settings.services.groq")} check={health.data.groq} />
            </ul>
          )}
        </Card>

        <Section title={t("settings.signins.title")} description={t("settings.signins.description")}>
          <Button variant="secondary" onClick={() => void logoutAll()} icon={<LogOut aria-hidden className="size-4" />}>{t("settings.signins.logoutAll")}</Button>
        </Section>
      </div>
    </div>
  );
}
