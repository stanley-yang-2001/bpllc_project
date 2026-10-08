// Runs before the page paints so a dark-mode user never sees a white flash.
// A separate file (not inline) because the Content-Security-Policy forbids inline scripts.
(function () {
  try {
    var saved = localStorage.getItem("tutor:theme");
    var dark = saved === "dark" || ((saved === null || saved === "system") && window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.classList.toggle("dark", dark);
  } catch (e) { /* storage blocked: stay light */ }
})();
