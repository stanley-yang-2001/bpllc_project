import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, type UseFormReturn } from "react-hook-form";
import { Link } from "react-router-dom";
import { Button, ErrorText, inputCls } from "../components/ui";
import { Field, PasswordField } from "./fields";
import { registerSchema, type RegisterValues } from "./schemas";

export const useRegisterForm = () =>
  useForm<RegisterValues>({ resolver: zodResolver(registerSchema), defaultValues: { language: "en", display_name: "", accept_privacy: false } });

type Language = { code: string; native: string };
const FALLBACK: Language[] = [{ code: "en", native: "English" }];

export function RegisterForm({ form, languages, onSubmit, serverError }: { form: UseFormReturn<RegisterValues>; languages: Language[]; onSubmit: (v: RegisterValues) => Promise<void>; serverError?: string }) {
  const { register, handleSubmit, formState: { errors, isSubmitting } } = form;
  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
      <Field id="r-name" label="Your name" error={errors.display_name?.message}>
        <input id="r-name" autoComplete="name" className={inputCls} {...register("display_name")} />
      </Field>
      <Field id="r-email" label="Email" error={errors.email?.message}>
        <input id="r-email" type="email" autoComplete="email" className={inputCls} {...register("email")} />
      </Field>
      <PasswordField id="r-pass" autoComplete="new-password" error={errors.password?.message} reg={register("password")} />
      <Field id="r-lang" label="Language I'm learning">
        <select id="r-lang" className={inputCls} {...register("language")}>
          {(languages.length ? languages : FALLBACK).map((l) => (
            <option key={l.code} value={l.code} lang={l.code}>{l.native}</option>
          ))}
        </select>
      </Field>

      <div>
        <label className="flex items-start gap-2.5 text-sm text-slate-700">
          <input type="checkbox" className="mt-0.5 size-4 shrink-0 rounded accent-brand-600" {...register("accept_privacy")} />
          <span>
            I have read and accept the{" "}
            <Link to="/privacy" target="_blank" rel="noopener" className="font-medium text-brand-600 underline underline-offset-2 dark:text-brand-200">Privacy Policy</Link>
          </span>
        </label>
        <ErrorText>{errors.accept_privacy?.message}</ErrorText>
        <p className="mt-2 text-xs text-slate-500">
          We keep your name and email to run your account, never sell them, and you can delete everything any time in Settings.
        </p>
      </div>

      <ErrorText>{serverError}</ErrorText>
      <Button type="submit" className="w-full" loading={isSubmitting}>Create account</Button>
    </form>
  );
}
