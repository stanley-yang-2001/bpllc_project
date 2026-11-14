export interface Garden { seeds: number; sprouts: number; trees: number }
export type Plot = "trees" | "sprouts" | "seeds";
/** At most this many pictures are drawn, so a big vocabulary does not make a huge page; the numbers below always show the full count. */
export const MAX_PLOTS = 120;

/** The pictures to draw: trees first, then sprouts, then seeds, shrunk in proportion when there are more than MAX_PLOTS words
 * (each stage keeps at least one picture while it has any words). */
export function gardenPlots(g: Garden): Plot[] {
  const total = g.trees + g.sprouts + g.seeds;
  const scale = total > MAX_PLOTS ? MAX_PLOTS / total : 1;
  const n = (v: number) => (v === 0 ? 0 : Math.max(1, Math.round(v * scale)));
  return [...Array<Plot>(n(g.trees)).fill("trees"), ...Array<Plot>(n(g.sprouts)).fill("sprouts"), ...Array<Plot>(n(g.seeds)).fill("seeds")];
}
