import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { Modal } from "./Modal";
import { Button } from "./ui";

export interface ConfirmOptions {
  title: string;
  body?: ReactNode;
  confirmLabel?: string;
  tone?: "danger" | "primary";
}
type Confirm = (o: ConfirmOptions) => Promise<boolean>;
const Ctx = createContext<Confirm | null>(null);

/** `if (await confirm({ title: "Delete 3 words?" })) ...`  Replaces the browser's plain confirm box. */
export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [opts, setOpts] = useState<ConfirmOptions | null>(null);
  const resolver = useRef<((v: boolean) => void) | null>(null);

  const confirm = useCallback<Confirm>((o) => new Promise<boolean>((resolve) => { resolver.current = resolve; setOpts(o); }), []);
  const finish = (answer: boolean) => { resolver.current?.(answer); resolver.current = null; setOpts(null); };

  return (
    <Ctx.Provider value={confirm}>
      {children}
      <Modal open={opts !== null} onClose={() => finish(false)} title={opts?.title ?? ""}>
        {opts?.body && <div className="mb-5 text-sm text-slate-600">{opts.body}</div>}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" data-autofocus onClick={() => finish(false)}>Cancel</Button>
          <Button variant={opts?.tone === "primary" ? "primary" : "danger"} onClick={() => finish(true)}>{opts?.confirmLabel ?? "Delete"}</Button>
        </div>
      </Modal>
    </Ctx.Provider>
  );
}

export function useConfirm(): Confirm {
  const v = useContext(Ctx);
  if (!v) throw new Error("useConfirm must be used inside <ConfirmProvider>");
  return v;
}
