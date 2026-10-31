import { useQuery } from "@tanstack/react-query";
import { Languages } from "lucide-react";
import { useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ThemeToggle } from "../components/ThemeToggle";
import { BrandPanel } from "../login/BrandPanel";
import { LoginForm, useLoginForm } from "../login/LoginForm";
import { RegisterForm, useRegisterForm } from "../login/RegisterForm";
import { useAuthRequest } from "../login/useAuthRequest";

/** The log-in / create-account page: the panel, the two tabs and whichever form is showing. The pieces are in login/. */
export default function Login() {
  const { user } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const { serverError, run, clearError } = useAuthRequest();
  const { data: languages = [] } = useQuery({ queryKey: ["languages"], queryFn: api.languages, staleTime: Infinity });
  const loginForm = useLoginForm();
  const registerForm = useRegisterForm();

  if (user) return <Navigate to="/" replace />;

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <BrandPanel />
      <main className="relative flex flex-col items-center justify-center px-4 py-12">
        <div className="absolute right-3 top-3"><ThemeToggle /></div>
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-2 text-xl font-semibold tracking-tight text-slate-900 lg:hidden">
            <span className="flex size-9 items-center justify-center rounded-lg bg-brand-600 text-white"><Languages aria-hidden className="size-5" /></span>
            Language Tutor
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{mode === "login" ? "Welcome back" : "Create your account"}</h1>
          <p className="mt-1 text-sm text-slate-600">{mode === "login" ? "Log in to keep learning." : "We only ask for your name and email."}</p>

          <div role="tablist" className="mb-6 mt-6 grid grid-cols-2 gap-1 rounded-lg bg-slate-100 p-1 text-sm">
            {(["login", "register"] as const).map((m) => (
              <button
                key={m}
                role="tab"
                aria-selected={mode === m}
                onClick={() => { setMode(m); clearError(); }}
                className={`rounded-md py-1.5 transition ${mode === m ? "bg-surface font-medium text-slate-900 shadow-xs" : "text-slate-600 hover:text-slate-900"}`}
              >
                {m === "login" ? "Log in" : "Create account"}
              </button>
            ))}
          </div>

          {mode === "login"
            ? <LoginForm form={loginForm} serverError={serverError} onSubmit={(v) => run(() => api.login(v))} />
            : <RegisterForm form={registerForm} languages={languages} serverError={serverError} onSubmit={(v) => run(() => api.register(v))} />}
        </div>
        <p className="mt-10 text-xs text-slate-500">
          <Link to="/privacy" className="underline-offset-2 hover:text-slate-900 hover:underline">Privacy Policy</Link>
        </p>
      </main>
    </div>
  );
}
