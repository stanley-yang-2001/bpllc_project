import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterEach } from "vitest";
import { setCurrentUserId } from "../api/client";

// A loaded machine (Docker running next to the tests) once timed out findBy* at the default 1000 ms and a whole test at 5000 ms,
// so a screen that needs a moment to appear gets a few seconds; a screen that never appears still fails, just later.
configure({ asyncUtilTimeout: 5000 });

// jsdom has <dialog> but not showModal()/close(); this gives tests the same open/close behaviour.
if (typeof HTMLDialogElement !== "undefined" && !HTMLDialogElement.prototype.showModal) {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    if (!this.hasAttribute("open")) return;
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  };
}

afterEach(() => {
  cleanup();
  setCurrentUserId(null);                 // module-level state must not leak between tests
});
