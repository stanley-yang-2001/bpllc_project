import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Card } from "../../components/ui";

/** The frame of one card on the practice menu: icon and title, a line of text, then the mode's own controls. */
export function ModeTile({ icon: Icon, title, text, children }: { icon: LucideIcon; title: string; text: string; children?: ReactNode }) {
  return (
    <Card className="space-y-3">
      <h2 className="flex items-center gap-2 font-semibold text-slate-900"><Icon aria-hidden className="size-5" />{title}</h2>
      <p className="text-sm text-slate-600">{text}</p>
      {children}
    </Card>
  );
}
