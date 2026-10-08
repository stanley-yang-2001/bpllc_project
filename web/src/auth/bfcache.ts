/** Browsers can restore a whole page from memory when you press Back ("back/forward cache"), including one
 * that was showing a learner's data before they logged out. A restored page is reloaded so it asks the
 * server who is logged in instead of showing what it remembers. */
export function installBfcacheGuard(target: Pick<Window, "addEventListener">, reload: () => void) {
  target.addEventListener("pageshow", (e) => {
    if ((e as PageTransitionEvent).persisted) reload();
  });
}
