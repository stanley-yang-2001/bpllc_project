/** The geometry of the colour wheel, kept apart from the component so it can be tested without a browser.
 * Hue is the angle clockwise from the top (the way a CSS conic-gradient runs); strength (saturation) is the distance
 * from the centre as a share of the radius. */
export interface Point { x: number; y: number }

export function pointToHueStrength(p: Point, centre: Point, radius: number): { h: number; s: number } {
  const dx = p.x - centre.x, dy = p.y - centre.y;
  const dist = Math.hypot(dx, dy);
  const h = ((Math.atan2(dx, -dy) * 180) / Math.PI + 360) % 360;
  return { h: dist === 0 ? 0 : h, s: Math.min(1, dist / radius) };
}
export function hueStrengthToPoint(h: number, s: number, centre: Point, radius: number): Point {
  const a = (h * Math.PI) / 180;
  return { x: centre.x + Math.sin(a) * s * radius, y: centre.y - Math.cos(a) * s * radius };
}
/** Keyboard: left and right turn the hue, up and down change the strength. `big` is the shifted, larger step. */
export function keyStep(key: string, h: number, s: number, big: boolean): { h: number; s: number } | null {
  const dh = big ? 15 : 3, ds = big ? 0.1 : 0.02;
  switch (key) {
    case "ArrowRight": return { h: (h + dh) % 360, s };
    case "ArrowLeft": return { h: (h - dh + 360) % 360, s };
    case "ArrowUp": return { h, s: Math.min(1, s + ds) };
    case "ArrowDown": return { h, s: Math.max(0, s - ds) };
    default: return null;
  }
}
