import { X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";

/** A dialog built on the browser's own <dialog>: it traps focus, closes on Escape, dims the page behind it
 * and hands focus back to whatever opened it, none of which we have to re-implement. */
export function Modal({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) {
      d.showModal();
      // React's autoFocus fires while the dialog is still closed (so it does nothing), and the browser would
      // then focus the first control, the close button. Put focus where the caller asked, after opening.
      d.querySelector<HTMLElement>("[data-autofocus]")?.focus();
    }
    if (!open && d.open) d.close();
  }, [open]);

  if (!open) return null;
  return (
    <dialog
      ref={ref}
      aria-labelledby="modal-title"
      onClose={onClose}                                         // fires for Escape and for close()
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}   // a click on the dimmed backdrop
      className="m-auto w-[calc(100%-2rem)] max-w-md rounded-xl border border-slate-200 bg-surface p-0 text-slate-900 shadow-xl backdrop:bg-slate-950/50 backdrop:backdrop-blur-sm"
    >
      <div className="p-6">
        <div className="mb-3 flex items-start justify-between gap-4">
          <h2 id="modal-title" className="text-lg font-semibold tracking-tight">{title}</h2>
          <button type="button" aria-label="Close dialog" onClick={onClose} className="-m-1 rounded-lg p-1 text-slate-500 hover:bg-slate-100 hover:text-slate-900">
            <X aria-hidden className="size-4.5" />
          </button>
        </div>
        {children}
      </div>
    </dialog>
  );
}
