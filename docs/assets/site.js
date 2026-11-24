// JavaScript comune del sito Roll&Play. I testi stanno in window.RNP, scritto dalla build.
(function(){
  "use strict";
  const $ = (s, r=document) => r.querySelector(s);
  const $$ = (s, r=document) => Array.from(r.querySelectorAll(s));

  // ---------- tema chiaro e scuro
  const THEME_KEY = "rnp-theme";
  const root = document.documentElement;
  function currentTheme(){
    if (root.dataset.theme) return root.dataset.theme;
    return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  $$(".theme-toggle").forEach(b => b.addEventListener("click", () => {
    const next = currentTheme() === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    try { localStorage.setItem(THEME_KEY, next); } catch(e){}
  }));
})();
