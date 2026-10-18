import { useEffect, useId, useRef, useState } from "react";
import { hexToHsv, hsvToHex, normalizeHex } from "./color";
import { hueStrengthToPoint, keyStep, pointToHueStrength } from "./wheel";

/** A colour wheel with no library: hue around, strength outward, a brightness slider and a hex box (the accessible
 * fallback). Works by pointer and touch (`touch-action: none`) and by keyboard (the wheel is a slider). */
export function ColorWheel({ value, onChange, label, brightnessLabel, hexLabel, spoken }: {
  value: string; onChange: (hex: string) => void; label: string; brightnessLabel: string; hexLabel: string;
  spoken: (h: number, s: number) => string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const hsv = hexToHsv(value);
  const hue = useRef(hsv.h);                        // keep the hue while the strength is zero (grey has no hue)
  if (hsv.s > 0 && hsv.v > 0) hue.current = hsv.h;
  const [text, setText] = useState(value);
  const [badHex, setBadHex] = useState(false);
  useEffect(() => { setText(value); setBadHex(false); }, [value]);
  const id = useId();

  const set = (h: number, s: number, v = hsv.v) => { hue.current = h; onChange(hsvToHex({ h, s, v })); };
  const fromPointer = (e: React.PointerEvent) => {
    const r = ref.current!.getBoundingClientRect();
    const radius = r.width / 2;
    const { h, s } = pointToHueStrength({ x: e.clientX, y: e.clientY }, { x: r.left + radius, y: r.top + radius }, radius);
    set(h, s);
  };
  const size = 100;                                  // the marker is placed in percent of the wheel, so it scales
  const m = hueStrengthToPoint(hue.current, hsv.s, { x: 50, y: 50 }, 50);

  return (
    <div className="flex flex-wrap items-start gap-5">
      <div
        ref={ref}
        role="slider"
        tabIndex={0}
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={359}
        aria-valuenow={Math.round(hue.current)}
        aria-valuetext={spoken(hue.current, hsv.s)}
        onPointerDown={(e) => { e.currentTarget.setPointerCapture?.(e.pointerId); fromPointer(e); }}
        onPointerMove={(e) => { if (e.buttons) fromPointer(e); }}
        onKeyDown={(e) => {
          const next = keyStep(e.key, hue.current, hsv.s, e.shiftKey);
          if (next) { e.preventDefault(); set(next.h, next.s); }
        }}
        className="relative size-44 shrink-0 cursor-crosshair touch-none rounded-full border border-slate-300 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500"
        style={{ background: "radial-gradient(circle closest-side, #fff, transparent), conic-gradient(from 0deg, hsl(0 100% 50%), hsl(60 100% 50%), hsl(120 100% 50%), hsl(180 100% 50%), hsl(240 100% 50%), hsl(300 100% 50%), hsl(360 100% 50%))" }}
      >
        <div aria-hidden className="pointer-events-none absolute inset-0 rounded-full bg-black" style={{ opacity: 1 - hsv.v }} />
        <span
          aria-hidden
          className="pointer-events-none absolute size-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white shadow-[0_0_0_1.5px_rgba(0,0,0,0.7)]"
          style={{ left: `${(m.x / size) * 100}%`, top: `${(m.y / size) * 100}%`, background: value }}
        />
      </div>
      <div className="min-w-48 flex-1 space-y-3">
        <div>
          <label htmlFor={`${id}-v`} className="mb-1 block text-sm font-medium text-slate-700">{brightnessLabel}</label>
          <input id={`${id}-v`} type="range" min={0} max={100} value={Math.round(hsv.v * 100)} className="w-full accent-brand-600"
            onChange={(e) => set(hue.current, hsv.s, Number(e.target.value) / 100)} />
        </div>
        <div>
          <label htmlFor={`${id}-hex`} className="mb-1 block text-sm font-medium text-slate-700">{hexLabel}</label>
          <input
            id={`${id}-hex`}
            value={text}
            spellCheck={false}
            autoComplete="off"
            aria-invalid={badHex}
            maxLength={7}
            className={`w-32 rounded-lg border bg-surface px-3 py-2 font-mono text-sm text-slate-900 shadow-xs ${badHex ? "border-red-500" : "border-slate-300"}`}
            onChange={(e) => {
              setText(e.target.value);
              const h = normalizeHex(e.target.value);
              setBadHex(!h && e.target.value !== "");
              if (h) onChange(h);
            }}
            onBlur={() => { setText(value); setBadHex(false); }}
          />
        </div>
      </div>
    </div>
  );
}
