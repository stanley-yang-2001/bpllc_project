import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, Eye, EyeOff, Languages, ShieldCheck, Sparkles } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate } from "react-router-dom";
import { z } from "zod";
import { api, ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ThemeToggle } from "../components/ThemeToggle";
import { Button, ErrorText, inputCls } from "../components/ui";

// Mirrors the server rules (the server is still the authority).
const email = z.string().trim().toLowerCase().email("Enter a valid email address").max(254);
const password = z
  .string()
  .min(8, "At least 8 characters")
  .refine((v) => new TextEncoder().encode(v).length <= 72, "At most 72 bytes");

const loginSchema = z.object({ email: z.string().trim().min(1, "Enter your email"), password: z.string().min(1, "Enter your password") });
const registerSchema = z.object({
  display_name: z.string().trim().min(1, "Enter your name").max(40, "At most 40 characters"),
  email,
  password,
  language: z.string().min(1),
  accept_privacy: z.boolean().refine((v) => v, "You need to accept the privacy policy to create an account"),
});
type LoginForm = z.infer<typeof loginSchema>;
type RegisterForm = z.infer<typeof registerSchema>;

function PasswordField({ id, autoComplete, error, reg }: { id: string; autoComplete: string; error?: string; reg: object }) {
  const [shown, setShown] = useState(false);
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-slate-700">Password</label>
      <div className="relative">
        <input id={id} type={shown ? "text" : "password"} autoComplete={autoComplete} className={`${inputCls} pr-10`} {...reg} />
        <button
          type="button"
          aria-label={shown ? "Hide password" : "Show password"}
          onClick={() => setShown((s) => !s)}
          className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-slate-500 hover:text-slate-800"
        >
          {shown ? <EyeOff aria-hidden className="size-4" /> : <Eye aria-hidden className="size-4" />}
        </button>
      </div>
      <ErrorText>{error}</ErrorText>
    </div>
  );
}

const Field = ({ id, label, error, children }: { id: string; label: string; error?: string; children: React.ReactNode }) => (
  <div>
    <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-slate-700">{label}</label>
    {children}
    <ErrorText>{error}</ErrorText>
  </div>
);

const points = [
  [BookOpen, "A separate word list for every language you study"],
  [Sparkles, "Stories written from the words you already know"],
  [ShieldCheck, "We keep only your name and email, and your words stay private"],
] as const;

export default function Login() {
  const { user, setUser } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [serverError, setServerError] = useState<string>();
  const { data: languages = [] } = useQuery({ queryKey: ["languages"], queryFn: api.languages, staleTime: Infinity });

  const loginForm = useForm<LoginForm>({ resolver: zodResolver(loginSchema) });
  const registerForm = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
    defaultValues: { language: "en", display_name: "", accept_privacy: false },
  });

  if (user) return <Navigate to="/" replace />;

  const run = async (fn: () => Promise<unknown>) => {
    setServerError(undefined);
    try {
      setUser((await fn()) as Parameters<typeof setUser>[0]);
    } catch (e) {
      setServerError(e instanceof ApiError ? e.message : "Something went wrong.");
    }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-gradient-to-br from-brand-700 via-brand-600 to-brand-900 p-12 text-white lg:flex">
        <div className="flex items-center gap-2 text-lg font-semibold tracking-tight">
          <span className="flex size-9 items-center justify-center rounded-lg bg-white/15"><Languages aria-hidden className="size-5" /></span>
          Language Tutor
        </div>
        <div>
          <p className="text-4xl font-semibold leading-tight tracking-tight">Learn with the words<br />you actually know.</p>
          <ul className="mt-8 space-y-4 text-brand-100">
            {points.map(([Icon, text]) => (
              <li key={text} className="flex items-start gap-3">
                <Icon aria-hidden className="mt-0.5 size-5 shrink-0 text-white" />
                <span>{text}</span>
              </li>
            ))}
          </ul>
        </div>
        <p className="text-sm text-brand-200">Runs on your own computer.</p>
        <div aria-hidden className="pointer-events-none absolute -right-24 -top-24 size-80 rounded-full bg-white/5" />
        <div aria-hidden className="pointer-events-none absolute -bottom-32 -left-16 size-96 rounded-full bg-white/5" />
      </aside>

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
                onClick={() => { setMode(m); setServerError(undefined); }}
                className={`rounded-md py-1.5 transition ${mode === m ? "bg-surface font-medium text-slate-900 shadow-xs" : "text-slate-600 hover:text-slate-900"}`}
              >
                {m === "login" ? "Log in" : "Create account"}
              </button>
            ))}
          </div>

          {mode === "login" ? (
            <form onSubmit={loginForm.handleSubmit((v) => run(() => api.login(v)))} className="space-y-4" noValidate>
              <Field id="l-email" label="Email" error={loginForm.formState.errors.email?.message}>
                <input id="l-email" type="email" autoComplete="email" className={inputCls} {...loginForm.register("email")} />
              </Field>
              <PasswordField id="l-pass" autoComplete="current-password" error={loginForm.formState.errors.password?.message} reg={loginForm.register("password")} />
              <ErrorText>{serverError}</ErrorText>
              <Button type="submit" className="w-full" loading={loginForm.formState.isSubmitting}>Log in</Button>
            </form>
          ) : (
            <form onSubmit={registerForm.handleSubmit((v) => run(() => api.register(v)))} className="space-y-4" noValidate>
              <Field id="r-name" label="Your name" error={registerForm.formState.errors.display_name?.message}>
                <input id="r-name" autoComplete="name" className={inputCls} {...registerForm.register("display_name")} />
              </Field>
              <Field id="r-email" label="Email" error={registerForm.formState.errors.email?.message}>
                <input id="r-email" type="email" autoComplete="email" className={inputCls} {...registerForm.register("email")} />
              </Field>
              <PasswordField id="r-pass" autoComplete="new-password" error={registerForm.formState.errors.password?.message} reg={registerForm.register("password")} />
              <Field id="r-lang" label="Language I'm learning">
                <select id="r-lang" className={inputCls} {...registerForm.register("language")}>
                  {(languages.length ? languages : [{ code: "en", name: "English" }]).map((l) => (
                    <option key={l.code} value={l.code}>{l.name}</option>
                  ))}
                </select>
              </Field>

              <div>
                <label className="flex items-start gap-2.5 text-sm text-slate-700">
                  <input type="checkbox" className="mt-0.5 size-4 shrink-0 rounded accent-brand-600" {...registerForm.register("accept_privacy")} />
                  <span>
                    I have read and accept the{" "}
                    <Link to="/privacy" target="_blank" rel="noopener" className="font-medium text-brand-600 underline underline-offset-2 dark:text-brand-200">Privacy Policy</Link>
                  </span>
                </label>
                <ErrorText>{registerForm.formState.errors.accept_privacy?.message}</ErrorText>
                <p className="mt-2 text-xs text-slate-500">
                  We keep your name and email to run your account, never sell them, and you can delete everything any time in Settings.
                </p>
              </div>

              <ErrorText>{serverError}</ErrorText>
              <Button type="submit" className="w-full" loading={registerForm.formState.isSubmitting}>Create account</Button>
            </form>
          )}
        </div>
        <p className="mt-10 text-xs text-slate-500">
          <Link to="/privacy" className="underline-offset-2 hover:text-slate-900 hover:underline">Privacy Policy</Link>
        </p>
      </main>
    </div>
  );
}
