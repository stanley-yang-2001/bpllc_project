import { Moon, Sun } from "lucide-react";
import { useTheme } from "../theme/ThemeProvider";

/** Quick light/dark switch. "Follow the system" lives in Settings → Appearance. */
export function ThemeToggle({ className = "" }: { className?: string }) {
  const { resolved, setTheme } = useTheme();
  const toDark = resolved === "light";
  return (
    <button
      type="button"
      aria-label={toDark ? "Switch to dark mode" : "Switch to light mode"}
      title={toDark ? "Dark mode" : "Light mode"}
      onClick={() => setTheme(toDark ? "dark" : "light")}
      className={`flex size-9 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 ${className}`}
    >
      {toDark ? <Moon aria-hidden className="size-4.5" /> : <Sun aria-hidden className="size-4.5" />}
    </button>
  );
}
