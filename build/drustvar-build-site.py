#!/usr/bin/env python3
"""Genera il sito HTML di Drustvar dal manuale in Markdown.
Uso: python drustvar-build-site.py "Drustvar - Roll&Play.md" "Drustvar - Roll&Play.html"
"""
import re, sys, html, json

SRC = sys.argv[1] if len(sys.argv) > 1 else "source.md"
OUT = sys.argv[2] if len(sys.argv) > 2 else "Drustvar - Roll&Play.html"

text = open(SRC, encoding="utf8").read()
text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)  # frontmatter
lines = text.split("\n")


def esc(s):
    return html.escape(s, quote=False)


def inline(s):
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    return s


def slug(s):
    s = re.sub(r"[^\w]+", "-", s.lower()).strip("-")
    return s


# ---------- split into H1 / H2 tree ----------
tree = []  # [{title, intro:[lines], subs:[{title, lines}]}]
for ln in lines:
    if ln.startswith("# "):
        tree.append({"title": ln[2:].strip(), "intro": [], "subs": []})
    elif ln.startswith("## "):
        tree[-1]["subs"].append({"title": ln[3:].strip(), "lines": []})
    elif tree:
        if tree[-1]["subs"]:
            tree[-1]["subs"][-1]["lines"].append(ln)
        else:
            tree[-1]["intro"].append(ln)


# ---------- block renderer ----------
def parse_items(block_lines):
    """Parse a bullet list (with 2-space nested items and continuation lines)."""
    items = []
    for ln in block_lines:
        m = re.match(r"^(\s*)- (.*)$", ln)
        if m:
            depth = len(m.group(1)) // 2
            item = {"text": m.group(2), "extra": [], "children": []}
            if depth == 0:
                items.append(item)
            else:
                items[-1]["children"].append(item)
        else:
            tgt = items[-1]["children"][-1] if items and items[-1]["children"] else items[-1]
            tgt["extra"].append(ln.strip())
    return items


def render_list(items, ordered=False):
    tag = "ol" if ordered else "ul"
    out = [f"<{tag}>"]
    for it in items:
        inner = inline(it["text"])
        for ex in it["extra"]:
            inner += "<br>" + inline(ex)
        if it["children"]:
            inner += render_list(it["children"])
        out.append(f"<li>{inner}</li>")
    out.append(f"</{tag}>")
    return "".join(out)


def blocks(block_lines):
    """Group lines into blocks: para, ul, ol, table, callout."""
    res, i = [], 0
    L = block_lines
    while i < len(L):
        ln = L[i]
        if not ln.strip():
            i += 1
            continue
        if re.match(r"^\s*- ", ln):
            j = i
            while j < len(L) and L[j].strip() and (re.match(r"^\s*- ", L[j]) or L[j].startswith("  ")):
                j += 1
            res.append(("ul", L[i:j]))
            i = j
        elif re.match(r"^\d+\. ", ln):
            j = i
            while j < len(L) and re.match(r"^\d+\. ", L[j]):
                j += 1
            res.append(("ol", L[i:j]))
            i = j
        elif ln.startswith("|"):
            j = i
            while j < len(L) and L[j].startswith("|"):
                j += 1
            res.append(("table", L[i:j]))
            i = j
        elif ln.startswith(">"):
            j = i
            while j < len(L) and L[j].startswith(">"):
                j += 1
            res.append(("callout", L[i:j]))
            i = j
        else:
            j = i
            while j < len(L) and L[j].strip() and not re.match(r"^(\s*- |\d+\. |\||>)", L[j]):
                j += 1
            res.append(("p", L[i:j]))
            i = j
    return res


def render_blocks(block_lines):
    out = []
    for kind, bl in blocks(block_lines):
        if kind == "p":
            out.append(f"<p>{inline(' '.join(x.strip() for x in bl))}</p>")
        elif kind == "ul":
            out.append(render_list(parse_items(bl)))
        elif kind == "ol":
            items = [{"text": re.sub(r"^\d+\. ", "", x), "extra": [], "children": []} for x in bl]
            out.append(render_list(items, ordered=True))
        elif kind == "table":
            rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in bl]
            rows = [r for r in rows if not all(re.fullmatch(r":?-+:?", c) for c in r)]
            head, body = rows[0], rows[1:]
            t = "<div class='table-wrap'><table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>"
            for r in body:
                t += "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>"
            out.append(t + "</tbody></table></div>")
        elif kind == "callout":
            content = [re.sub(r"^>\s?", "", x) for x in bl]
            title = "Nota"
            m = re.match(r"\[!\w+\]\s*(.*)", content[0])
            if m:
                title = m.group(1) or title
                content = content[1:]
            body = "".join(f"<p>{inline(c)}</p>" for c in content if c.strip())
            out.append(f"<aside class='callout'><div class='callout-title'>{inline(title)}</div>{body}</aside>")
    return "".join(out)


# ---------- interactive creation ----------
def name_and_param(item_text):
    m = re.match(r"\*\*(.+?):\*\*\s*(.*)$", item_text)
    name, desc = (m.group(1), m.group(2)) if m else (item_text, "")
    pm = re.match(r"^(.*?)\s*\((.+)\)$", name)
    base, param = (pm.group(1), pm.group(2)) if pm else (name, None)
    return name, base, param, desc


def example_options(desc):
    m = re.search(r"a scelta(?:, per esempio| tra)\s+(.+?)\.\s*$", desc)
    if not m:
        return None, desc
    raw = m.group(1)
    parts = re.split(r",\s*|\s+o\s+|\s+e\s+", raw)
    parts = [p.strip() for p in parts if p.strip()]
    open_ended = "per esempio" in m.group(0)
    return (parts, open_ended), desc


STEP_RE = re.compile(r"Passo (\d+): Scegli (?:una|un) (\w+) \((\w+)\)")
step_lists = {}  # step key -> list of option names (for cross references)
creation_meta = []


def collect_names(sub):
    first = [b for b in blocks(sub["lines"]) if b[0] == "ul"]
    names = []
    for _, bl in first:
        for it in parse_items(bl):
            _, base, _, _ = name_and_param(it["text"])
            names.append(base)
    return names


creation = next(s for s in tree if s["title"].startswith("Creazione"))
for sub in creation["subs"]:
    m = STEP_RE.match(sub["title"])
    if m:
        step_lists[m.group(2)] = collect_names(sub)


def cap(s):
    return s[:1].upper() + s[1:] if s else s


def option_card(group, it, stepcat, typ, disabled=False):
    full, base, param, desc = name_and_param(it["text"])
    desc = cap(desc)
    oid = f"{group}-{slug(full)}"
    sub_html = ""
    data_param = ""
    # nested forms (Abomination)
    if it["children"]:
        forms = []
        for ch in it["children"]:
            cfull, cbase, cparam, cdesc = name_and_param(ch["text"])
            extra_select = ""
            for ex in ch["extra"]:
                bm = re.match(r"Bestie conosciute:\s*(.+?)\.?$", ex)
                if bm:
                    beasts = [b.strip() for b in bm.group(1).split(",")]
                    opts = "".join(f"<option>{esc(b)}</option>" for b in beasts)
                    extra_select = (f"<label class='sub-label'>Bestia <select data-sub='{group}' data-subkey='bestia'>"
                                    f"<option value=''>scegli…</option>{opts}</select></label>")
            cdesc_full = cap(cdesc) + "".join(" " + e for e in ch["extra"] if not e.startswith("Bestie"))
            fid = f"{oid}-{slug(cparam or cfull)}"
            forms.append(
                f"<div class='form-opt'><input type='radio' name='{group}-form' value='{esc(cfull)}' data-form='{group}' id='{fid}'>"
                f"<span class='form-name'>{esc(cparam or cfull)}</span>"
                f"<span class='form-desc'>{inline(cdesc_full)}</span>{extra_select}</div>")
        sub_html = f"<div class='subchoice'><div class='sub-title'>Scegli la forma</div>{''.join(forms)}</div>"
    elif param:
        opts, open_ended = None, True
        found, _ = example_options(desc)
        if found:
            opts, open_ended = found
        elif param in step_lists:
            opts, open_ended = step_lists[param], False
        elif param == "Vocazione":
            opts, open_ended = step_lists.get("Vocazione", []), False
        options = "".join(f"<option>{esc(o)}</option>" for o in (opts or []))
        other = "<option value='__altro'>Altro…</option>" if open_ended else ""
        sub_html = (f"<div class='subchoice'><label class='sub-label'>{esc(param)} "
                    f"<select data-sub='{group}' data-subkey='{esc(param)}'><option value=''>scegli…</option>{options}{other}</select></label>"
                    f"<input class='other-input' type='text' placeholder='Scrivi la tua scelta' data-other='{group}' hidden></div>")
        data_param = f" data-param='{esc(param)}'"
    dis = " disabled" if disabled else ""
    note = "<span class='badge'>solo con l'Esperienza</span>" if disabled else ""
    return (f"<div class='option{' is-disabled' if disabled else ''}' data-group='{group}'>"
            f"<div class='option-head'><input type='radio' name='{group}' value='{esc(base)}' id='{oid}'{data_param}{dis}>"
            f"<span class='option-name'>{esc(full)}</span>{note}</div>"
            f"<div class='option-desc'>{inline(desc)}</div>{sub_html}</div>")


def render_step(sub, idx):
    title = sub["title"]
    m = STEP_RE.match(title)
    if title.startswith("Passo 0"):
        body = render_blocks(sub["lines"])
        body += ("<div class='field'><label for='hero-name'>Nome dell'Eroe</label>"
                 "<input id='hero-name' type='text' data-field='nome' placeholder='Es. John Ryan Welsh'></div>"
                 "<div class='field'><label for='hero-goal'>Obiettivo</label>"
                 "<textarea id='hero-goal' rows='2' data-field='obiettivo' placeholder='Cosa vuole cambiare del Mondo?'></textarea></div>")
        creation_meta.append({"key": "nome", "label": "Nome", "type": ""})
        creation_meta.append({"key": "obiettivo", "label": "Obiettivo", "type": ""})
        return body
    if not m:
        return render_blocks(sub["lines"])
    cat, typ = m.group(2), m.group(3)
    group = slug(cat)
    creation_meta.append({"key": group, "label": cat, "type": typ})
    out = []
    lst_count = 0
    for kind, bl in blocks(sub["lines"]):
        if kind == "ul":
            items = parse_items(bl)
            cards = []
            for it in items:
                _, base, _, _ = name_and_param(it["text"])
                cards.append(option_card(group, it, cat, typ, disabled=(base == "Maestro")))
            out.append(f"<div class='options'>{''.join(cards)}</div>")
            lst_count += 1
        elif kind == "p":
            out.append(f"<p>{inline(' '.join(x.strip() for x in bl))}</p>")
        else:
            out.append(render_blocks(bl))
    return "".join(out)


# ---------- assemble ----------
sections_html = []
for si, sec in enumerate(tree):
    is_creation = sec["title"].startswith("Creazione")
    intro = render_blocks(sec["intro"])
    subs = []
    for sub in sec["subs"]:
        body = render_step(sub, 0) if is_creation else render_blocks(sub["lines"])
        sid = slug(sub["title"])
        subs.append(f"<details class='sub' id='{sid}'><summary><span class='sub-h'>{inline(sub['title'])}</span></summary>"
                    f"<div class='sub-body'>{body}</div></details>")
    extra = ""
    if is_creation:
        extra = ("<section class='sheet' id='scheda' aria-live='polite'>"
                 "<h3>La tua scheda</h3><dl id='sheet-list'></dl>"
                 "<div class='sheet-actions'><button type='button' id='copy-sheet'>Copia scheda</button>"
                 "<button type='button' id='reset-sheet' class='ghost'>Azzera</button></div>"
                 "<p class='sheet-msg' id='sheet-msg'></p></section>")
    sections_html.append(
        f"<details class='top' name='capitoli' id='{slug(sec['title'])}'>"
        f"<summary><span class='num'>{['I','II','III','IV','V','VI'][si]}</span><span class='top-h'>{inline(sec['title'])}</span></summary>"
        f"<div class='top-body'>{intro}{''.join(subs)}{extra}</div></details>")

HTML = r"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Drustvar · Roll &amp; Play</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@400;700&family=Cormorant+Garamond:ital,wght@0,500;0,600;0,700;1,500&family=Source+Sans+3:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
<style>
:root{
  --paper:#dfe6ec; --paper-2:#d2dbe3; --card:#eef2f5; --ink:#1b1f27; --ink-soft:#3f4754;
  --line:#a9b6c3; --accent:#6b1d27; --accent-soft:#8a3a44; --gold:#8a7348; --focus:#2f4b66;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font:400 17px/1.6 "Source Sans 3",system-ui,sans-serif;
  background-image:radial-gradient(ellipse at top,rgba(255,255,255,.45),transparent 60%),radial-gradient(ellipse at bottom,rgba(27,31,39,.08),transparent 70%);
  background-attachment:fixed}
.wrap{max-width:780px;margin:0 auto;padding:28px 16px 80px}
header.masthead{text-align:center;padding:24px 0 30px}
.masthead .kicker{font:600 .78rem/1 "Source Sans 3",sans-serif;letter-spacing:.35em;text-transform:uppercase;color:var(--ink-soft)}
.masthead h1{font:700 clamp(2.4rem,9vw,4rem)/1.05 "Cinzel Decorative",serif;margin:.25em 0 .1em;letter-spacing:.02em}
.masthead .sub{font:italic 500 1.2rem/1.3 "Cormorant Garamond",serif;color:var(--ink-soft)}
.ornament{display:flex;align-items:center;gap:12px;justify-content:center;color:var(--accent);margin:18px auto 0;max-width:340px}
.ornament::before,.ornament::after{content:"";flex:1;height:1px;background:linear-gradient(90deg,transparent,var(--ink-soft),transparent)}
details.top{border-top:1px solid var(--line);}
details.top:last-of-type{border-bottom:1px solid var(--line)}
details summary{list-style:none;cursor:pointer;-webkit-tap-highlight-color:transparent}
details summary::-webkit-details-marker{display:none}
details.top>summary{display:flex;align-items:baseline;gap:14px;padding:18px 4px}
.num{font:700 .95rem/1 "Cormorant Garamond",serif;color:var(--accent);min-width:2.2em;letter-spacing:.08em}
.top-h{font:700 clamp(1.35rem,5vw,1.85rem)/1.2 "Cinzel Decorative",serif;flex:1}
details.top>summary::after,details.sub>summary::after{content:"+";font:400 1.5rem/1 "Cormorant Garamond",serif;color:var(--accent);transition:transform .2s}
details[open]>summary::after{content:"\2212"}
.top-body{padding:0 4px 28px}
details.sub{border-left:2px solid var(--line);margin:10px 0;padding-left:14px;transition:border-color .2s}
details.sub[open]{border-left-color:var(--accent)}
details.sub>summary{display:flex;align-items:baseline;gap:10px;padding:8px 0}
.sub-h{font:700 1.36rem/1.25 "Cormorant Garamond",serif;flex:1}
.sub-body{padding:2px 0 12px}
p{margin:.6em 0}
strong{font-weight:600}
em{font-style:italic;color:var(--ink-soft)}
ul,ol{padding-left:1.25em;margin:.6em 0}
li{margin:.35em 0}
li::marker{color:var(--accent)}
.table-wrap{overflow-x:auto;margin:12px 0}
table{border-collapse:collapse;width:100%;font-size:.95rem;background:var(--card)}
th,td{border:1px solid var(--line);padding:6px 10px;text-align:left}
th{font:700 1.08rem/1.2 "Cormorant Garamond",serif;background:var(--paper-2)}
.callout{margin:16px 0;padding:12px 16px;background:var(--card);border-left:3px solid var(--accent);}
.callout-title{font:700 1.18rem/1.2 "Cormorant Garamond",serif;color:var(--accent);margin-bottom:4px}
.callout p{margin:.3em 0}
/* creation */
.options{display:grid;gap:10px;margin:14px 0}
.option{cursor:pointer;background:var(--card);border:1px solid var(--line);border-radius:3px;padding:12px 14px;transition:border-color .15s,box-shadow .15s}
.option:has(> .option-head input:checked){border-color:var(--accent);box-shadow:0 0 0 1px var(--accent),0 6px 18px -10px rgba(27,31,39,.5)}
.option.is-disabled{opacity:.6;cursor:not-allowed}
.subchoice{cursor:default}
.option-desc{cursor:pointer}
.option-head{display:flex;align-items:center;gap:10px;cursor:pointer}
.option-head input{accent-color:var(--accent);width:18px;height:18px;flex:none}
.option-name{font:700 1.24rem/1.2 "Cormorant Garamond",serif}
.badge{font-size:.72rem;letter-spacing:.06em;text-transform:uppercase;color:var(--accent);border:1px solid var(--accent-soft);padding:1px 6px;border-radius:2px;margin-left:auto}
.option-desc{margin:6px 0 0 28px;font-size:.96rem;color:var(--ink-soft)}
.subchoice{margin:10px 0 0 28px;display:none}
.option:has(> .option-head input:checked) .subchoice{display:block}
.sub-title{font:600 .78rem/1 "Source Sans 3",sans-serif;letter-spacing:.18em;text-transform:uppercase;color:var(--accent);margin:6px 0}
.form-opt{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;align-items:start;padding:8px 0;border-top:1px dashed var(--line);cursor:pointer}
.form-opt input{accent-color:var(--accent);margin-top:4px}
.form-name{font:700 1.12rem/1.3 "Cormorant Garamond",serif}
.form-desc{grid-column:2;font-size:.92rem;color:var(--ink-soft)}
.form-opt .sub-label{grid-column:2}
.sub-label{display:flex;flex-wrap:wrap;align-items:center;gap:8px;font-size:.9rem;color:var(--ink-soft)}
select,input[type=text],textarea{font:inherit;color:var(--ink);background:#f7f9fb;border:1px solid var(--line);border-radius:2px;padding:6px 8px;max-width:100%}
.other-input{margin-top:8px;width:100%}
select:focus,input:focus,textarea:focus,button:focus-visible,summary:focus-visible{outline:2px solid var(--focus);outline-offset:2px}
.field{margin:12px 0;display:grid;gap:4px}
.field label{font:700 1.14rem/1.2 "Cormorant Garamond",serif}
.field input,.field textarea{width:100%}
.sheet{margin-top:24px;padding:18px;background:var(--ink);color:#e9edf1;border-radius:3px}
.sheet h3{margin:0 0 10px;font:700 1.3rem/1.2 "Cinzel Decorative",serif;color:#fff}
.sheet dl{display:grid;grid-template-columns:auto 1fr;gap:6px 14px;margin:0}
.sheet dt{font:700 1.06rem/1.4 "Cormorant Garamond",serif;color:#c7b48f}
.sheet dt small{display:block;font:400 .72rem/1 "Source Sans 3",sans-serif;letter-spacing:.1em;text-transform:uppercase;color:#93a0ad}
.sheet dd{margin:0}
.sheet dd.empty{color:#7f8b97;font-style:italic}
.sheet-actions{display:flex;gap:10px;margin-top:14px;flex-wrap:wrap}
button{font:600 .95rem/1 "Source Sans 3",sans-serif;padding:10px 14px;border-radius:2px;border:1px solid #c7b48f;background:#c7b48f;color:var(--ink);cursor:pointer}
button.ghost{background:transparent;color:#e9edf1;border-color:#5a6573}
.sheet-msg{min-height:1.2em;font-size:.85rem;color:#c7b48f;margin:8px 0 0}
footer{text-align:center;color:var(--ink-soft);font:italic 500 1rem "Cormorant Garamond",serif;margin-top:40px}
@media (max-width:520px){
  body{font-size:16px}
  .option-desc,.subchoice{margin-left:0}
  .sheet dl{grid-template-columns:1fr}
  .sheet dt{margin-top:6px}
}
</style>
</head>
<body>
<div class="wrap">
<header class="masthead">
  <div class="kicker">Roll &amp; Play</div>
  <h1>Drustvar</h1>
  <div class="sub">Manuale di campagna</div>
  <div class="ornament">✠</div>
</header>
<main>
__SECTIONS__
</main>
<footer>Che il Mondo vi resista.</footer>
</div>
<script>
const META = __META__;
const KEY = "drustvar-scheda-v1";
const $ = (s, r=document) => r.querySelector(s);
const $$ = (s, r=document) => Array.from(r.querySelectorAll(s));

// exclusive top-level accordion (fallback for browsers without details[name])
$$("details.top").forEach(d => d.addEventListener("toggle", () => {
  if (d.open) $$("details.top").forEach(o => { if (o !== d) o.open = false; });
}));

function load(){ try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch(e){ return {}; } }
function save(st){ try { localStorage.setItem(KEY, JSON.stringify(st)); } catch(e){} }

function readState(){
  const st = {};
  $$("[data-field]").forEach(el => st[el.dataset.field] = el.value);
  META.forEach(m => {
    if (!m.type) return;
    const r = $(`input[name="${m.key}"]:checked`);
    if (!r) return;
    const box = r.closest(".option");
    const entry = {value: r.value};
    const form = $(`input[name="${m.key}-form"]:checked`, box);
    if (form) entry.form = form.value;
    const sels = $$(`select[data-sub="${m.key}"]`, box).filter(s => !s.closest(".form-opt") || s.closest(".form-opt").querySelector("input").checked);
    sels.forEach(s => {
      let v = s.value;
      if (v === "__altro") { const o = $(`input[data-other="${m.key}"]`, box); v = o ? o.value : ""; entry.other = v; }
      if (v) entry[s.dataset.subkey] = v;
    });
    st[m.key] = entry;
  });
  return st;
}

function label(entry){
  if (!entry) return "";
  if (entry.form){
    let t = entry.form;
    if (entry.bestia) t += " · " + entry.bestia;
    return t;
  }
  const extras = Object.keys(entry).filter(k => !["value","other","form"].includes(k)).map(k => entry[k]);
  return extras.length ? `${entry.value} (${extras.join(", ")})` : entry.value;
}

function renderSheet(st){
  const dl = $("#sheet-list"); if (!dl) return;
  dl.innerHTML = "";
  META.forEach(m => {
    const dt = document.createElement("dt");
    dt.innerHTML = m.label + (m.type ? `<small>${m.type}</small>` : "");
    const dd = document.createElement("dd");
    const v = m.type ? label(st[m.key]) : (st[m.key] || "");
    dd.textContent = v || "da scegliere";
    if (!v) dd.className = "empty";
    dl.append(dt, dd);
  });
}

function update(){
  $$("select[data-sub]").forEach(s => {
    const o = s.closest(".subchoice") && $(`input[data-other="${s.dataset.sub}"]`, s.closest(".subchoice"));
    if (o) o.hidden = s.value !== "__altro";
  });
  const st = readState(); save(st); renderSheet(st);
}

function restore(){
  const st = load();
  $$("[data-field]").forEach(el => { if (st[el.dataset.field]) el.value = st[el.dataset.field]; });
  META.forEach(m => {
    const e = st[m.key]; if (!m.type || !e) return;
    const r = $$(`input[name="${m.key}"]`).find(x => x.value === e.value); if (!r) return;
    r.checked = true;
    const box = r.closest(".option");
    if (e.form){ const f = $$(`input[name="${m.key}-form"]`, box).find(x => x.value === e.form); if (f) f.checked = true; }
    $$(`select[data-sub="${m.key}"]`, box).forEach(s => {
      const v = e[s.dataset.subkey]; if (!v) return;
      if ([...s.options].some(o => o.value === v || o.text === v)) s.value = v;
      else { s.value = "__altro"; const o = $(`input[data-other="${m.key}"]`, box); if (o) o.value = v; }
    });
  });
}

// Click anywhere on a card to select it; click again to deselect.
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
    const box = r.closest(".option");
    box.querySelectorAll(".form-opt input[type=radio]").forEach(f => f.checked = false);
  }
  update();
});
document.addEventListener("change", e => { if (e.target.matches("select, input[type=text]")) update(); });
document.addEventListener("input", e => { if (e.target.matches("[data-field],[data-other]")) update(); });

$("#copy-sheet")?.addEventListener("click", async () => {
  const st = readState();
  const txt = META.map(m => `${m.label}${m.type ? " ("+m.type+")" : ""}: ${(m.type ? label(st[m.key]) : st[m.key]) || "-"}`).join("\n");
  const msg = $("#sheet-msg");
  try { await navigator.clipboard.writeText(txt); msg.textContent = "Scheda copiata."; }
  catch(e){ msg.textContent = "Copia non riuscita: seleziona il testo a mano."; }
});
$("#reset-sheet")?.addEventListener("click", () => {
  $$(".top-body input[type=radio]").forEach(r => r.checked = false);
  $$("select[data-sub]").forEach(s => s.value = "");
  $$("[data-field],[data-other]").forEach(i => i.value = "");
  update();
});

restore(); update();
</script>
</body>
</html>
"""

out = HTML.replace("__SECTIONS__", "\n".join(sections_html)).replace("__META__", json.dumps(creation_meta, ensure_ascii=False))
open(OUT, "w", encoding="utf8").write(out)
print("ok", OUT, len(out))
