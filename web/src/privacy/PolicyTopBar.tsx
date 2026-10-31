import { ArrowLeft, Languages } from "lucide-react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ThemeToggle } from "../components/ThemeToggle";
import { useI18n } from "../i18n/I18nProvider";

/** The bar above the policy: back to the app (or to sign-in), the name and the theme switch. */
export function PolicyTopBar() {
  const { user } = useAuth();
  const { t } = useI18n();
  return (
    <header className="border-b border-slate-200 bg-surface">
      <div className="mx-auto flex h-14 max-w-3xl items-center justify-between px-4">
        <Link to={user ? "/settings" : "/login"} className="flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-900">
          <ArrowLeft aria-hidden className="size-4" />
          {user ? t("privacy.backApp") : t("privacy.backSignIn")}
        </Link>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-2 text-sm font-semibold tracking-tight text-slate-900">
            <span className="flex size-7 items-center justify-center rounded-md bg-brand-600 text-white"><Languages aria-hidden className="size-4" /></span>
            Language Tutor
          </span>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
