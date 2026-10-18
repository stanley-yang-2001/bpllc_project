import { describe, expect, it } from "vitest";
import { hueStrengthToPoint, keyStep, pointToHueStrength } from "./wheel";

const c = { x: 100, y: 100 };
describe("wheel geometry", () => {
  it("reads hue clockwise from the top and strength as share of the radius", () => {
    expect(pointToHueStrength({ x: 100, y: 0 }, c, 100)).toEqual({ h: 0, s: 1 });          // top: red
    const right = pointToHueStrength({ x: 200, y: 100 }, c, 100);
    expect(right.h).toBeCloseTo(90); expect(right.s).toBeCloseTo(1);
    expect(pointToHueStrength({ x: 100, y: 200 }, c, 100).h).toBeCloseTo(180);
    expect(pointToHueStrength({ x: 0, y: 100 }, c, 100).h).toBeCloseTo(270);
    expect(pointToHueStrength({ x: 100, y: 50 }, c, 100).s).toBeCloseTo(0.5);
  });
  it("caps the strength at the edge and gives hue 0 at the centre", () => {
    expect(pointToHueStrength({ x: 500, y: 100 }, c, 100).s).toBe(1);
    expect(pointToHueStrength(c, c, 100)).toEqual({ h: 0, s: 0 });
  });
  it("is the inverse of itself", () => {
    for (const [h, s] of [[0, 1], [45, 0.3], [200, 0.8], [359, 0.5]]) {
      const back = pointToHueStrength(hueStrengthToPoint(h, s, c, 100), c, 100);
      expect(back.h).toBeCloseTo(h, 5); expect(back.s).toBeCloseTo(s, 5);
    }
  });
  it("steps with the arrow keys, wrapping the hue and clamping the strength", () => {
    expect(keyStep("ArrowRight", 359, 0.5, false)).toEqual({ h: 2, s: 0.5 });
    expect(keyStep("ArrowLeft", 0, 0.5, false)).toEqual({ h: 357, s: 0.5 });
    expect(keyStep("ArrowUp", 10, 0.99, true)!.s).toBe(1);
    expect(keyStep("ArrowDown", 10, 0.01, false)!.s).toBe(0);
    expect(keyStep("ArrowRight", 0, 0, true)!.h).toBe(15);
    expect(keyStep("a", 0, 0, false)).toBeNull();
  });
});
