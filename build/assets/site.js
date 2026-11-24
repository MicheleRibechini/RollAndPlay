// JavaScript comune del sito Roll&Play. I testi stanno in window.RNP, scritto dalla build.
(function(){
  "use strict";
  const $ = (s, r=document) => r.querySelector(s);
  const $$ = (s, r=document) => Array.from(r.querySelectorAll(s));
  const RNP = window.RNP || {};

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

  // ---------- sezioni a fisarmonica: aprendone una si chiudono le altre
  $$("details.top").forEach(d => d.addEventListener("toggle", () => {
    if (d.open) $$("details.top").forEach(o => { if (o !== d) o.open = false; });
  }));
  // un indirizzo con #sezione apre la sezione e le sue genitrici
  function openHash(){
    const id = decodeURIComponent(location.hash.slice(1));
    const el = id && document.getElementById(id);
    if (!el) return;
    for (let d = el.closest("details"); d; d = d.parentElement.closest("details")) d.open = true;
    el.scrollIntoView();
  }
  addEventListener("hashchange", openHash);
  openHash();

  // ---------- creazione interattiva
  const C = RNP.creation;
  if (!C) return;
  const UI = RNP.ui;
  const META = C.meta, LABELS = C.labels;

  function load(){ try { return JSON.parse(localStorage.getItem(C.key)) || {}; } catch(e){ return {}; } }
  function save(st){ try { localStorage.setItem(C.key, JSON.stringify(st)); } catch(e){} }

  // le selezioni attive di una scheda: escluse quelle dentro una forma non scelta
  function activeSelects(box, cat){
    return $$(`select[data-sub="${cat}"]`, box).filter(s => {
      const f = s.closest(".form-opt");
      return !f || f.querySelector("input[type=radio]").checked;
    });
  }

  function readState(){
    const st = {v: 2, picks: {}};
    $$("[data-field]").forEach(el => st[el.dataset.field] = el.value);
    META.forEach(m => {
      if (!m.type) return;
      const r = $(`input[name="${m.key}"]:checked`);
      if (!r) return;
      const box = r.closest(".option");
      const e = {code: r.value, sub: {}, other: {}};
      const f = $(`input[name="${m.key}-form"]:checked`, box);
      if (f) e.form = f.value;
      activeSelects(box, m.key).forEach(s => {
        const k = s.dataset.key;
        if (s.value === "__other") {
          const o = $(`input[data-other="${m.key}"][data-key="${k}"]`, box);
          if (o && o.value) e.other[k] = o.value;
        } else if (s.value) e.sub[k] = s.value;
      });
      st.picks[m.key] = e;
    });
    return st;
  }

  function labelOf(cat, e){
    if (!e) return "";
    const box = $(`input[name="${cat}"][value="${e.code}"]`)?.closest(".option");
    const subLabel = k => {
      const s = box && $(`select[data-sub="${cat}"][data-key="${k}"]`, box);
      return s ? (LABELS[`${s.dataset.ns}/${e.sub[k]}`] || e.sub[k]) : e.sub[k];
    };
    const extras = Object.keys(e.sub || {}).map(subLabel).concat(Object.values(e.other || {}));
    if (e.form) {
      const t = LABELS[`${cat}/${e.code}/${e.form}`] || e.form;
      return extras.length ? `${t} · ${extras.join(", ")}` : t;
    }
    const base = LABELS[`${cat}/${e.code}`] || e.code;
    const plain = base.replace(/\s*\(.*\)$/, "");
    return extras.length ? `${plain} (${extras.join(", ")})` : base;
  }

  function valueOf(m, st){ return m.type ? labelOf(m.key, st.picks[m.key]) : (st[m.key] || ""); }

  function renderSheet(st){
    const dl = $("#sheet-list"); if (!dl) return;
    dl.innerHTML = "";
    META.forEach(m => {
      const dt = document.createElement("dt");
      dt.textContent = m.label;
      if (m.type) { const sm = document.createElement("small"); sm.textContent = m.type; dt.append(sm); }
      const dd = document.createElement("dd");
      const v = valueOf(m, st);
      dd.textContent = v || UI.to_choose;
      if (!v) dd.className = "empty";
      dl.append(dt, dd);
    });
  }

  function update(){
    $$("select[data-sub]").forEach(s => {
      const o = $(`input[data-other="${s.dataset.sub}"][data-key="${s.dataset.key}"]`, s.closest(".subchoice"));
      if (o) o.hidden = s.value !== "__other";
    });
    const st = readState(); save(st); renderSheet(st);
  }

  function restore(){
    const st = load();
    if (st.v !== 2) return;
    $$("[data-field]").forEach(el => { if (st[el.dataset.field]) el.value = st[el.dataset.field]; });
    META.forEach(m => {
      const e = st.picks && st.picks[m.key]; if (!m.type || !e) return;
      const r = $(`input[name="${m.key}"][value="${e.code}"]`); if (!r || r.disabled) return;
      r.checked = true;
      const box = r.closest(".option");
      if (e.form) { const f = $(`input[name="${m.key}-form"][value="${e.form}"]`, box); if (f) f.checked = true; }
      $$(`select[data-sub="${m.key}"]`, box).forEach(s => {
        const k = s.dataset.key;
        if (e.sub && e.sub[k] && [...s.options].some(o => o.value === e.sub[k])) s.value = e.sub[k];
        else if (e.other && e.other[k]) {
          s.value = "__other";
          const o = $(`input[data-other="${m.key}"][data-key="${k}"]`, box); if (o) o.value = e.other[k];
        }
      });
    });
  }

  // clic su tutta la scheda dell'opzione per sceglierla, di nuovo per toglierla
  let pressed = null;
  function radioFor(target){
    if (target.closest("select, textarea, input[type=text], option")) return null;
    const form = target.closest(".form-opt");
    if (form) return form.querySelector("input[type=radio]");
    if (target.closest(".subchoice")) return null;
    const opt = target.closest(".option");
    return opt ? opt.querySelector(".option-head input[type=radio]") : null;
  }
  function remember(e){ const r = radioFor(e.target); pressed = r ? {r, was: r.checked} : null; }
  document.addEventListener("pointerdown", remember, true);
  document.addEventListener("keydown", e => { if (e.key === " " || e.key === "Enter") remember(e); }, true);
  document.addEventListener("click", e => {
    const r = radioFor(e.target);
    if (!r || r.disabled) return;
    const was = pressed && pressed.r === r ? pressed.was : r.checked && e.target !== r;
    pressed = null;
    r.checked = !was;
    if (!r.checked && !r.name.endsWith("-form")) {
      r.closest(".option").querySelectorAll(".form-opt input[type=radio]").forEach(f => f.checked = false);
    }
    update();
  });
  document.addEventListener("change", e => { if (e.target.matches("select[data-sub]")) update(); });
  document.addEventListener("input", e => { if (e.target.matches("[data-field],[data-other]")) update(); });

  $("#copy-sheet")?.addEventListener("click", async () => {
    const st = readState();
    const txt = META.map(m => `${m.label}${m.type ? " (" + m.type + ")" : ""}: ${valueOf(m, st) || "-"}`).join("\n");
    const msg = $("#sheet-msg");
    try { await navigator.clipboard.writeText(txt); msg.textContent = UI.sheet_copied; }
    catch(e){ msg.textContent = UI.sheet_copy_failed; }
  });
  $("#reset-sheet")?.addEventListener("click", () => {
    $$(".top-body input[type=radio]").forEach(r => r.checked = false);
    $$("select[data-sub]").forEach(s => s.value = "");
    $$("[data-field],[data-other]").forEach(i => i.value = "");
    $("#sheet-msg").textContent = "";
    update();
  });

  restore(); update();
})();
