import { Navigate } from "react-router-dom";
import { Layout } from "../components/Layout";
import { ConfirmProvider } from "../components/Confirm";
import { ToastProvider } from "../components/Toast";
import { Spinner } from "../components/ui";
import { ActiveLanguageProvider } from "./ActiveLanguage";
import { useAuth } from "./AuthContext";

export function ProtectedLayout() {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace />;
  // keyed by user id: a different learner on the same browser starts with fresh language state
  return (
    <ActiveLanguageProvider key={user.id}>
      <ToastProvider>
        <ConfirmProvider>
          <Layout />
        </ConfirmProvider>
      </ToastProvider>
    </ActiveLanguageProvider>
  );
}
