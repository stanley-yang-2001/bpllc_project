import { Hammer, SearchX } from "lucide-react";
import { Badge, Card, EmptyState, PageHeader } from "../components/ui";

/** Honest stand-in for pages whose milestone is not built yet. */
export function ComingSoon({ title, milestone, note }: { title: string; milestone: string; note: string }) {
  return (
    <div>
      <PageHeader title={title} actions={<Badge tone="accent">Planned: {milestone}</Badge>} />
      <Card>
        <EmptyState icon={<Hammer aria-hidden className="size-5" />} title="Not built yet">
          {note}
        </EmptyState>
      </Card>
    </div>
  );
}

export function NotFound() {
  return (
    <Card>
      <EmptyState icon={<SearchX aria-hidden className="size-5" />} title="Page not found">
        That page doesn't exist. Use the menu above to find your way back.
      </EmptyState>
    </Card>
  );
}
