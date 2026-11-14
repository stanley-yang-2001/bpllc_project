import { Component, type ReactNode } from "react";

/** Wraps something that is nice to have (a streak chip, a toast, a rewards card) so that if it ever fails to draw, only it disappears and
 * the rest of the page keeps working. Shows nothing on failure. */
export class Quiet extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(error: unknown) { console.warn("A decoration failed to draw and was hidden:", error); }
  render() { return this.state.failed ? null : this.props.children; }
}
