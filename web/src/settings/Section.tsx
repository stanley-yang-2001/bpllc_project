import { type ReactNode } from "react";
import { Card } from "../components/ui";

export function Section({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <Card>
      <h2 className="font-semibold text-slate-900">{title}</h2>
      {description && <p className="mt-1 text-sm text-slate-600">{description}</p>}
      <div className="mt-4">{children}</div>
    </Card>
  );
}

export const Label = ({ htmlFor, children }: { htmlFor: string; children: ReactNode }) => (
  <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium text-slate-700">{children}</label>
);
