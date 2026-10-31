import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, type UseFormReturn } from "react-hook-form";
import { Button, ErrorText, inputCls } from "../components/ui";
import { Field, PasswordField } from "./fields";
import { loginSchema, type LoginValues } from "./schemas";

/** The form's state lives in the page (so it survives switching tabs); the form only draws it. */
export const useLoginForm = () => useForm<LoginValues>({ resolver: zodResolver(loginSchema) });

export function LoginForm({ form, onSubmit, serverError }: { form: UseFormReturn<LoginValues>; onSubmit: (v: LoginValues) => Promise<void>; serverError?: string }) {
  const { register, handleSubmit, formState: { errors, isSubmitting } } = form;
  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
      <Field id="l-email" label="Email" error={errors.email?.message}>
        <input id="l-email" type="email" autoComplete="email" className={inputCls} {...register("email")} />
      </Field>
      <PasswordField id="l-pass" autoComplete="current-password" error={errors.password?.message} reg={register("password")} />
      <ErrorText>{serverError}</ErrorText>
      <Button type="submit" className="w-full" loading={isSubmitting}>Log in</Button>
    </form>
  );
}
