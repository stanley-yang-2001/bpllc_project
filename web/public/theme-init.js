// Runs before the page paints so nobody sees a flash of the wrong colours.
// A separate file (not inline) because the Content-Security-Policy forbids inline scripts.
// It is a plain applier: it reads the device copy of the account's display preferences (written by the app, which
// also does all the colour maths) and applies it. Colours go through style.setProperty, which the CSP allows.
(function () {
  try {
    var root = document.documentElement;
    var copy = null;
    try { copy = JSON.parse(localStorage.getItem("tutor:prefs:cache")); } catch (e) { copy = null; }
    if (!copy || typeof copy !== "object") copy = null;
    var theme = copy && typeof copy.theme === "string" ? copy.theme : "system";
    if (!copy) {
      // Nobody signed in on this device: the light/dark switch on the sign-in and policy pages is remembered for this tab only.
      try { var tab = sessionStorage.getItem("tutor:theme:tab"); if (tab === "light" || tab === "dark") theme = tab; } catch (e) { /* blocked */ }
    }
    var dark;
    if (copy && copy.vars && typeof copy.vars === "object" && (copy.base === "dark" || copy.base === "light")) {
      for (var name in copy.vars) {
        if (Object.prototype.hasOwnProperty.call(copy.vars, name) && name.indexOf("--") === 0 && typeof copy.vars[name] === "string") {
          root.style.setProperty(name, copy.vars[name]);
        }
      }
      dark = copy.base === "dark";
    } else {
      dark = theme === "dark" || (theme !== "light" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    }
    root.classList.toggle("dark", dark);
  } catch (e) { /* storage blocked: stay light */ }
})();
