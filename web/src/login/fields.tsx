import { Eye, EyeOff } from "lucide-react";
import { useState, type ReactNode } from "react";
import { ErrorText, inputCls } from "../components/ui";

/** A label, its control and the error under it. */
export const Field = ({ id, label, error, children }: { id: string; label: string; error?: string; children: ReactNode }) => (
  <div>
    <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-slate-700">{label}</label>
    {children}
    <ErrorText>{error}</ErrorText>
  </div>
);

/** A password box with a show/hide button. `reg` is what react-hook-form's register() returned. */
export function PasswordField({ id, autoComplete, error, reg }: { id: string; autoComplete: string; error?: string; reg: object }) {
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
