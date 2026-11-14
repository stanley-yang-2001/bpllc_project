import { Flame, PartyPopper, Sparkles, Trophy } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { DURATION_MS, PARTICLES, type Level } from "./effects";
import { useRewards } from "./useRewards";

type Celebrate = (level: Level, text: string) => void;
const Ctx = createContext<Celebrate>(() => undefined);

/** Lets any page say "celebrate this" (`useCelebrate()(level, text)`). Nothing is shown when the learner turned rewards off, and under
 * "reduce motion" only the label appears (no moving pieces). Effects are drawn with CSS only, so they cost nothing when idle. */
export function useCelebrate(): Celebrate { return useContext(Ctx); }

const COLOURS = ["#6366f1", "#f59e0b", "#10b981", "#ec4899", "#38bdf8", "#facc15"];
const calm = () => { try { return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false; } catch { return false; } };

interface Show { id: number; level: Level; text: string }

export function CelebrationProvider({ children }: { children: ReactNode }) {
  const { data } = useRewards();
  const off = data?.show_rewards === false;
  const [show, setShow] = useState<Show | null>(null);
  const next = useRef(1);
  const timer = useRef<number | undefined>(undefined);
  const current = useRef<Level>(1);

  const celebrate = useCallback<Celebrate>((level, text) => {
    if (off) return;
    if (timer.current !== undefined && level < current.current) return;       // a bigger one is still playing
    window.clearTimeout(timer.current);
    current.current = level;
    setShow({ id: next.current++, level, text });
    timer.current = window.setTimeout(() => { timer.current = undefined; setShow(null); }, DURATION_MS[level]);
  }, [off]);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  return <Ctx.Provider value={celebrate}>{children}{show && <Burst key={show.id} {...show} />}</Ctx.Provider>;
}

function Burst({ level, text }: Show) {
  const still = calm();
  const pieces = useMemo(() => {
    if (still) return [];
    return Array.from({ length: PARTICLES[level] }, (_, i) => {
      const angle = Math.random() * Math.PI * 2;
      const dist = 120 + Math.random() * (180 + level * 60);
      return {
        i, colour: COLOURS[i % COLOURS.length], round: i % 3 === 0,
        x: Math.cos(angle) * dist, y: Math.sin(angle) * dist - 80, spin: Math.round(Math.random() * 720 - 360),
        delay: Math.round(Math.random() * (level >= 5 ? 900 : 250)), size: 6 + Math.round(Math.random() * 6),
      };
    });
  }, [level, still]);
  const Icon = level >= 5 ? Trophy : level >= 4 ? PartyPopper : level >= 2 ? Sparkles : Flame;
  return (
    <div aria-hidden={false} className="pointer-events-none fixed inset-0 z-40 overflow-hidden" data-testid="celebration" data-level={level}>
      {level >= 4 && !still && <div className={`fx-glow ${level >= 5 ? "fx-flash" : ""}`} aria-hidden />}
      <div className="absolute left-1/2 top-1/3" aria-hidden>
        {pieces.map((p) => (
          <span key={p.i} className="fx-piece" style={{
            background: p.colour, width: p.size, height: p.round ? p.size : p.size * 0.5, borderRadius: p.round ? "9999px" : 2,
            ["--x" as string]: `${p.x}px`, ["--y" as string]: `${p.y}px`, ["--r" as string]: `${p.spin}deg`, animationDelay: `${p.delay}ms`,
          }} />
        ))}
      </div>
      <div className="absolute inset-x-0 top-1/4 flex justify-center px-4">
        <p role="status" className={`fx-pill fx-pill-${level} flex items-center gap-2 rounded-full bg-slate-900 px-5 py-2 font-semibold text-white shadow-xl dark:text-slate-100`}>
          <Icon aria-hidden className={level >= 3 ? "size-6 text-amber-300 dark:text-amber-600" : "size-5 text-amber-300 dark:text-amber-600"} />{text}
        </p>
      </div>
    </div>
  );
}
