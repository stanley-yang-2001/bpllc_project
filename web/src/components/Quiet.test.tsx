import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Quiet } from "./Quiet";

function Boom(): never { throw new Error("no"); }

describe("Quiet", () => {
  it("hides a part that fails to draw and keeps the rest", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    render(<div><Quiet><Boom /></Quiet><p>the page</p></div>);
    expect(screen.getByText("the page")).toBeInTheDocument();
  });
  it("shows its children normally", () => {
    render(<Quiet><p>chip</p></Quiet>);
    expect(screen.getByText("chip")).toBeInTheDocument();
  });
});
