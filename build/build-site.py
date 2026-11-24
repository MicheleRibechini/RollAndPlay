#!/usr/bin/env python3
"""Build del sito Roll&Play, comune a tutti i setting.

Legge i MANUAL e i THEME dal vault e genera tutto il sito in docs/.
Uso e opzioni: vedi build/README.md.
"""
import argparse
import html
import json
import re
import shutil
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent


# =====================================================================
# Utilita
# =====================================================================

def esc(s):
    return html.escape(s, quote=True)


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def roman(n):
    vals = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for v, r in vals:
        while n >= v:
            out += r
            n -= v
    return out


def read_text(path):
    return Path(path).read_text(encoding="utf8").replace("\r\n", "\n")


def warn(msg):
    print("ATTENZIONE:", msg, file=sys.stderr)


# =====================================================================
# Markdown (sottoinsieme usato nei MANUAL)
# =====================================================================

def clean_markdown(text):
    """Toglie frontmatter e commenti %%...%%."""
    text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)
    text = re.sub(r"%%.*?%%", "", text, flags=re.S)
    return text


def inline(s):
    s = esc(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    return s


def parse_page(text):
    """Divide un MANUAL in titolo (#), apertura, sezioni (##) e sottosezioni (###)."""
    page = {"title": "", "intro": [], "sections": []}
    for ln in clean_markdown(text).split("\n"):
        if ln.startswith("# "):
            page["title"] = ln[2:].strip()
        elif ln.startswith("## "):
            page["sections"].append({"title": ln[3:].strip(), "intro": [], "subs": []})
        elif ln.startswith("### ") and page["sections"]:
            page["sections"][-1]["subs"].append({"title": ln[4:].strip(), "lines": []})
        elif page["sections"]:
            sec = page["sections"][-1]
            (sec["subs"][-1]["lines"] if sec["subs"] else sec["intro"]).append(ln)
        else:
            page["intro"].append(ln)
    return page


def is_empty(lines):
    return not any(ln.strip() for ln in lines)


def parse_items(block_lines):
    """Elenco puntato con voci annidate di due spazi e righe di continuazione."""
    items = []
    for ln in block_lines:
        m = re.match(r"^(\s*)- (.*)$", ln)
        if m:
            item = {"text": m.group(2), "extra": [], "children": []}
            if len(m.group(1)) // 2 == 0 or not items:
                items.append(item)
            else:
                items[-1]["children"].append(item)
        elif items:
            tgt = items[-1]["children"][-1] if items[-1]["children"] else items[-1]
            tgt["extra"].append(ln.strip())
    return items


def blocks(lines):
    """Raggruppa le righe in blocchi: p, h4, ul, ol, table, callout."""
    res, i, L = [], 0, lines
    starts = r"^(\s*- |\d+\. |\||>|#### )"
    while i < len(L):
        ln = L[i]
        if not ln.strip():
            i += 1
        elif ln.startswith("#### "):
            res.append(("h4", [ln[5:].strip()]))
            i += 1
        elif re.match(r"^\s*- ", ln):
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
        else:
            for kind, pre in (("table", "|"), ("callout", ">")):
                if ln.startswith(pre):
                    j = i
                    while j < len(L) and L[j].startswith(pre):
                        j += 1
                    res.append((kind, L[i:j]))
                    i = j
                    break
            else:
                j = i
                while j < len(L) and L[j].strip() and not re.match(starts, L[j]):
                    j += 1
                res.append(("p", L[i:j]))
                i = j
    return res


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


def render_table(rows_raw):
    rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows_raw]
    rows = [r for r in rows if not all(re.fullmatch(r":?-+:?", c) for c in r)]
    head, body = rows[0], rows[1:]
    t = "<div class='table-wrap'><table><thead><tr>"
    t += "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>"
    for r in body:
        t += "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>"
    return t + "</tbody></table></div>"


def render_callout(lines):
    content = [re.sub(r"^>\s?", "", x) for x in lines]
    kind, title = "note", ""
    m = re.match(r"\[!(\w+)\]\s*(.*)", content[0])
    if m:
        kind, title = m.group(1).lower(), m.group(2)
        content = content[1:]
    head = f"<div class='callout-title'>{inline(title)}</div>" if title else ""
    return f"<aside class='callout callout-{esc(kind)}'>{head}{render_blocks(content)}</aside>"


def render_blocks(lines):
    out = []
    for kind, bl in blocks(lines):
        if kind == "p":
            out.append(f"<p>{inline(' '.join(x.strip() for x in bl))}</p>")
        elif kind == "h4":
            out.append(f"<h4>{inline(bl[0])}</h4>")
        elif kind == "ul":
            out.append(render_list(parse_items(bl)))
        elif kind == "ol":
            items = [{"text": re.sub(r"^\d+\. ", "", x), "extra": [], "children": []} for x in bl]
            out.append(render_list(items, ordered=True))
        elif kind == "table":
            out.append(render_table(bl))
        elif kind == "callout":
            out.append(render_callout(bl))
    return "".join(out)


# =====================================================================
# Tema: palette dai THEME
# =====================================================================

THEME_MODES = {"chiaro": "light", "scuro": "dark"}  # titoli ### del THEME


def read_palette(path):
    """Legge le tabelle di palette di un THEME: {light: {var: colore}, dark: {...}}."""
    pal = {"light": {}, "dark": {}}
    if not path or not Path(path).exists():
        return pal
    mode = None
    for ln in read_text(path).split("\n"):
        if ln.startswith("#"):
            mode = None
            for word, m in THEME_MODES.items():
                if ln.startswith("### ") and word in ln.lower():
                    mode = m
        elif mode and ln.startswith("|"):
            m = re.search(r"`(--[\w-]+)`.*?`(#[0-9a-fA-F]{3,8}|rgba?\([^`]*\))`", ln)
            if m:
                pal[mode][m.group(1)] = m.group(2)
    return pal


def palette_css(pal, selector_light=":root", selector_dark=':root[data-theme="dark"]'):
    def decl(d):
        return ";".join(f"{k}:{v}" for k, v in d.items())
    css = []
    if pal["light"]:
        css.append(f"{selector_light}{{{decl(pal['light'])}}}")
    if pal["dark"]:
        css.append(f"{selector_dark}{{{decl(pal['dark'])}}}")
        auto = ':root:not([data-theme="light"])' if selector_light == ":root" else selector_light
        css.append(f"@media (prefers-color-scheme: dark){{{auto}{{{decl(pal['dark'])}}}}}")
    return "\n".join(css)


# =====================================================================
# Creazione interattiva
# =====================================================================

class Creation:
    """Trasforma la sezione di creazione in opzioni con codici indipendenti dalla lingua."""

    def __init__(self, section, lang, disabled_codes):
        self.sec = section
        self.P = {k: re.compile(v) for k, v in lang["parse"].items()
                  if k not in ("creation_prefix", "examples_open")}
        self.open_word = lang["parse"]["examples_open"]
        self.terms = lang["terms"]
        self.ui = lang["ui"]
        self.disabled = set(disabled_codes)
        self.meta = [{"key": "name", "label": self.ui["sheet_name"], "type": ""},
                     {"key": "goal", "label": self.ui["sheet_goal"], "type": ""}]
        self.labels = {}          # "namespace/codice" -> etichetta
        self.lists = {}           # parola della categoria -> [(codice, nome)]
        for sub in section["subs"]:
            m = self.P["step"].match(sub["title"])
            if m:
                self.lists[m.group(2)] = [(self.code(base), base) for _, base, _, _ in self.names(sub)]

    def code(self, word):
        return self.terms.get(word, slug(word))

    @staticmethod
    def split_name(item_text):
        m = re.match(r"\*\*(.+?):\*\*\s*(.*)$", item_text)
        full, desc = (m.group(1), m.group(2)) if m else (item_text, "")
        pm = re.match(r"^(.*?)\s*\((.+)\)$", full)
        base, param = (pm.group(1), pm.group(2)) if pm else (full, None)
        return full, base, param, desc[:1].upper() + desc[1:]

    def names(self, sub):
        out = []
        for kind, bl in blocks(sub["lines"]):
            if kind == "ul":
                out += [self.split_name(it["text"]) for it in parse_items(bl)]
        return out

    def label(self, ns, code, text):
        self.labels[f"{ns}/{code}"] = text

    def select(self, cat, key, options, open_ended, ns):
        ui = self.ui
        opts = "".join(f"<option value='{esc(c)}'>{esc(t)}</option>" for c, t in options)
        for c, t in options:
            self.label(ns, c, t)
        other = f"<option value='__other'>{esc(ui['other'])}</option>" if open_ended else ""
        return (f"<select data-sub='{cat}' data-key='{esc(key)}' data-ns='{esc(ns)}'>"
                f"<option value=''>{esc(ui['choose'])}</option>{opts}{other}</select>")

    def option(self, cat, it):
        ui = self.ui
        full, base, param, desc = self.split_name(it["text"])
        code = self.code(base)
        self.label(cat, code, full)
        disabled = code in self.disabled
        sub_html = ""
        if it["children"]:
            forms = []
            for ch in it["children"]:
                cfull, cbase, cparam, cdesc = self.split_name(ch["text"])
                fcode = self.code(cparam or cfull)
                self.label(f"{cat}/{code}", fcode, cfull)
                beast, extra = "", []
                for ex in ch["extra"]:
                    bm = self.P["beasts"].match(ex)
                    if bm:
                        names = [b.strip() for b in bm.group(1).split(",") if b.strip()]
                        beast = (f"<label class='sub-label'>{esc(ui['beast'])} "
                                 + self.select(cat, "beast", [(slug(re.sub(r"\s*\(.*\)$", "", b)), b) for b in names],
                                             False, "beast")
                                 + "</label>")
                    else:
                        extra.append(ex)
                text = " ".join([cdesc] + extra)
                forms.append(
                    f"<div class='form-opt'><input type='radio' name='{cat}-form' value='{fcode}'"
                    f" aria-label='{esc(cparam or cfull)}'>"
                    f"<span class='form-name'>{esc(cparam or cfull)}</span>"
                    f"<span class='form-desc'>{inline(text)}</span>{beast}</div>")
            sub_html = (f"<div class='subchoice'><div class='sub-title'>{esc(ui['form_title'])}</div>"
                        f"{''.join(forms)}</div>")
        elif param:
            key = self.code(param)
            m = self.P["examples"].search(desc)
            if m:
                parts = [p.strip() for p in self.P["list_split"].split(m.group(1)) if p.strip()]
                options, open_ended, ns = [(slug(p), p) for p in parts], self.open_word in m.group(0), key
            elif param in self.lists:
                options, open_ended, ns = self.lists[param], False, self.code(param)
            else:
                options, open_ended, ns = [], True, key
            sub_html = (f"<div class='subchoice'><label class='sub-label'>{esc(param)} "
                        + self.select(cat, key, options, open_ended, ns) + "</label>"
                        f"<input class='other-input' type='text' placeholder='{esc(ui['other_placeholder'])}'"
                        f" data-other='{cat}' data-key='{esc(key)}' hidden></div>")
        dis = " disabled" if disabled else ""
        badge = f"<span class='badge'>{esc(ui['only_experience'])}</span>" if disabled else ""
        return (f"<div class='option{' is-disabled' if disabled else ''}' data-cat='{cat}'>"
                f"<div class='option-head'><input type='radio' name='{cat}' value='{code}'"
                f" aria-label='{esc(full)}'{dis}>"
                f"<span class='option-name'>{esc(full)}</span>{badge}</div>"
                f"<div class='option-desc'>{inline(desc)}</div>{sub_html}</div>")

    def step(self, sub):
        ui = self.ui
        if self.P["step_zero"].match(sub["title"]):
            return render_blocks(sub["lines"]) + (
                f"<div class='field'><label for='hero-name'>{esc(ui['hero_name'])}</label>"
                f"<input id='hero-name' type='text' data-field='name' placeholder='{esc(ui['hero_name_placeholder'])}'></div>"
                f"<div class='field'><label for='hero-goal'>{esc(ui['hero_goal'])}</label>"
                f"<textarea id='hero-goal' rows='2' data-field='goal' placeholder='{esc(ui['hero_goal_placeholder'])}'></textarea></div>")
        m = self.P["step"].match(sub["title"])
        if not m:
            return render_blocks(sub["lines"])
        cat_word, type_word = m.group(2), m.group(3)
        cat = self.code(cat_word)
        self.meta.append({"key": cat, "label": cat_word, "type": type_word})
        out = []
        for kind, bl in blocks(sub["lines"]):
            if kind == "ul":
                out.append("<div class='options'>"
                           + "".join(self.option(cat, it) for it in parse_items(bl)) + "</div>")
            else:
                out.append(render_blocks(bl))
        return "".join(out)

    def sheet(self):
        ui = self.ui
        return (f"<section class='sheet' id='sheet' aria-live='polite'><h3>{esc(ui['sheet_title'])}</h3>"
                f"<dl id='sheet-list'></dl><div class='sheet-actions'>"
                f"<button type='button' id='copy-sheet'>{esc(ui['copy_sheet'])}</button>"
                f"<button type='button' id='reset-sheet' class='ghost'>{esc(ui['reset_sheet'])}</button></div>"
                f"<p class='sheet-msg' id='sheet-msg'></p></section>")

    def data(self, storage_key):
        return {"key": storage_key, "meta": self.meta, "labels": self.labels}


# =====================================================================
# Pagine
# =====================================================================

class Site:
    def __init__(self, vault, out, manual_overrides):
        self.vault = Path(vault)
        self.out = Path(out)
        self.overrides = manual_overrides
        self.config = json.loads(read_text(HERE / "site.json"))
        self.css = read_text(HERE / "assets" / "site.css")
        self.js = read_text(HERE / "assets" / "site.js")
        self.palette = read_palette(self.vault / "system" / "RNP-THEME.md")
        if not self.palette["light"]:
            sys.exit("RNP-THEME: palette chiara non trovata.")
        if not self.palette["dark"]:
            warn("RNP-THEME: palette scura non definita, il tema scuro usa la chiara.")
        self.settings = self.find_settings()

    # ---------- sorgenti

    def find_settings(self):
        """Ogni cartella settings/<nome>/ con un <NOME>-MANUAL.md e un setting."""
        res = []
        for d in sorted((self.vault / "settings").iterdir()):
            manual = d / f"{d.name.upper()}-MANUAL.md"
            if d.is_dir() and manual.exists():
                code = slug(d.name)
                res.append({"code": code, "dir": d,
                            "manual": Path(self.overrides.get(code, manual)),
                            "test": code in self.overrides,
                            "theme": d / f"{d.name.upper()}-THEME.md"})
        return res

    def lang(self, code):
        return json.loads(read_text(HERE / "i18n" / f"{code}.json"))

    # ---------- pezzi comuni

    def prefix(self, lang_code, depth):
        """Percorso relativo verso la radice di docs/ da una pagina."""
        extra = 0 if lang_code == self.config["default_language"] else 1
        return "../" * (depth + extra)

    def placeholder(self, ui, text):
        return (f"<div class='placeholder'><span class='ph-label'>{esc(ui['placeholder_label'])}</span>"
                f"<p>{esc(text)}</p></div>")

    def shell(self, L, root, title, topbar, header, main, extra_css="", data=None):
        ui = L["ui"]
        data_js = f"<script>window.RNP={json.dumps(data, ensure_ascii=False)};</script>" if data else ""
        return f"""<!doctype html>
<html lang="{L['lang']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<script>try{{var t=localStorage.getItem("rnp-theme");if(t)document.documentElement.dataset.theme=t}}catch(e){{}}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@400;700&family=Cormorant+Garamond:ital,wght@0,500;0,700;1,500&family=Source+Sans+3:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{root}assets/site.css">{f'<style>{extra_css}</style>' if extra_css else ''}
</head>
<body>
<nav class="topbar">{topbar}<button type="button" class="theme-toggle" aria-label="{esc(ui['theme_toggle'])}" title="{esc(ui['theme_toggle'])}"><svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><circle cx="10" cy="10" r="8" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M10 2a8 8 0 0 1 0 16z" fill="currentColor"/></svg></button></nav>
<div class="wrap">
{header}
<main>
{main}
</main>
<footer>{esc(ui['footer'])}</footer>
</div>
{data_js}<script src="{root}assets/site.js"></script>
</body>
</html>
"""

    @staticmethod
    def masthead(title, subtitle, kicker=""):
        k = f"<div class='kicker'>{esc(kicker)}</div>" if kicker else ""
        return (f"<header class='masthead'>{k}"
                f"<h1>{esc(title)}</h1><div class='sub'>{esc(subtitle)}</div>"
                f"<div class='ornament' aria-hidden='true'>✠</div></header>")

    @staticmethod
    def image_placeholder(ui):
        """Segnaposto neutro per l'immagine del setting: nessuna immagine vera."""
        return ("<figure><svg viewBox='0 0 160 70' preserveAspectRatio='xMidYMid slice' role='img'"
                f" aria-label='{esc(ui['image_placeholder'])}'>"
                "<rect width='160' height='70' style='fill:var(--paper-2)'/>"
                "<path d='M0 70 L160 0 M0 0 L160 70' style='stroke:var(--line);stroke-width:.4'/>"
                "<text x='80' y='41' text-anchor='middle' font-size='14' style='fill:var(--accent)'>✠</text></svg>"
                f"<figcaption>{esc(ui['image_placeholder'])}</figcaption></figure>")

    def setting_info(self, L, s):
        """Nome dal # del MANUAL, descrizione dal paragrafo di apertura prima del primo ##."""
        page = parse_page(read_text(s["manual"]))
        name = page["title"] or s["code"].capitalize()
        para = next((b for k, b in blocks(page["intro"]) if k == "p"), None)
        desc = inline(" ".join(x.strip() for x in para)) if para else None
        return page, name, desc

    def manual_block(self, ui, lines, subs, placeholder_text):
        """Corpo di una sezione ## di RNP-MANUAL in home: sottosezioni ### come titoli."""
        if is_empty(lines) and not subs:
            return self.placeholder(ui, placeholder_text)
        out = render_blocks(lines)
        for sub in subs:
            out += f"<h3>{inline(sub['title'])}</h3>" + render_blocks(sub["lines"])
        return out

    # ---------- home

    def home(self, L):
        """Home a scorrimento: introduzione, setting, come si gioca, contatti."""
        ui, ph = L["ui"], L["placeholders"]
        root = self.prefix(L["lang"], 0)
        manual = parse_page(read_text(self.vault / "system" / "RNP-MANUAL.md"))
        found = {"intro": None, "play": None}
        for sec in manual["sections"]:
            for key, title in L["manual_sections"].items():
                if sec["title"] == title:
                    found[key] = sec
            if sec["title"] not in L["manual_sections"].values():
                warn(f"RNP-MANUAL: sezione '{sec['title']}' non prevista in home, ignorata.")

        def block(key):
            sec = found[key]
            return self.manual_block(ui, sec["intro"] if sec else [], sec["subs"] if sec else [], ph[key])

        cards = []
        for s in self.settings:
            _, name, desc = self.setting_info(L, s)
            tag = f" <span class='tag'>{esc(ui['test_label'])}</span>" if s["test"] else ""
            d = (f"<p class='card-desc'>{desc}{tag}</p>" if desc else
                 f"<p class='card-desc'><span class='ph-label'>{esc(ui['placeholder_label'])}</span> "
                 f"{esc(ph['setting_description'])}</p>")
            cards.append(f"<a class='setting-card' href='{s['code']}/'>{self.image_placeholder(ui)}"
                         f"<div class='card-body'><span class='card-name'>{esc(name)}</span>{d}"
                         f"<span class='card-cta'>{esc(ui['open_setting'])}</span></div></a>")

        contacts = []
        for c in self.config["contacts"]:
            if c.get("url"):
                contacts.append(f"<li><a href='{esc(c['url'])}'>{esc(c['label'])}</a></li>")
            else:
                contacts.append(f"<li>{esc(c['label'])}</li>")
        contacts_html = self.placeholder(ui, ph["contacts"]) if any(c.get("placeholder") for c in self.config["contacts"]) else ""
        contacts_html += f"<ul class='contacts'>{''.join(contacts)}</ul>"

        parts = [("intro", ui["nav_intro"], block("intro")),
                 ("settings", ui["nav_settings"], f"<div class='settings'>{''.join(cards)}</div>"),
                 ("play", ui["nav_play"], block("play")),
                 ("contacts", ui["nav_contacts"], contacts_html)]
        main = "".join(f"<section class='home-sec' id='{k}'><h2 class='sec-h'><span class='num'>{roman(i)}</span>"
                       f"<span>{esc(t)}</span></h2>{body}</section>" for i, (k, t, body) in enumerate(parts, 1))
        topbar = "<div class='links'>" + "".join(f"<a href='#{k}'>{esc(t)}</a>" for k, t, _ in parts) + "</div>"
        header = self.masthead(ui["home_title"], ui["home_subtitle"])
        return self.shell(L, root, ui["home_title"], topbar, header, main)

    # ---------- pagina del setting

    def setting_page(self, L, s):
        """Setting, creazione dell'eroe, regole speciali: sezioni ## a fisarmonica, ### apribili."""
        ui, ph = L["ui"], L["placeholders"]
        root = self.prefix(L["lang"], 1)
        page, name, _ = self.setting_info(L, s)
        sections = page["sections"] or [{"title": t, "intro": [], "subs": []} for t in L["placeholder_sections"]]
        creation, out = None, []
        for i, sec in enumerate(sections, 1):
            is_creation = sec["title"].startswith(L["parse"]["creation_prefix"])
            if is_creation and sec["subs"]:
                creation = Creation(sec, L, self.config["creation_disabled"])
            body = render_blocks(sec["intro"])
            for sub in sec["subs"]:
                inner = creation.step(sub) if is_creation and creation else render_blocks(sub["lines"])
                out_sub = (f"<details class='sub' id='{slug(sub['title'])}'><summary><span class='sub-h'>"
                           f"{inline(sub['title'])}</span></summary><div class='sub-body'>{inner}</div></details>")
                body += out_sub
            if not body:
                body = self.placeholder(ui, ph["setting_section"])
            if is_creation and creation:
                body += creation.sheet()
            out.append(f"<details class='top' name='sezioni' id='{slug(sec['title'])}'>"
                       f"<summary><span class='num'>{roman(i)}</span><span class='top-h'>{inline(sec['title'])}</span>"
                       f"</summary><div class='top-body'>{body}</div></details>")

        lead = render_blocks(page["intro"])
        note = (f"<p class='test-note'><span class='tag'>{esc(ui['test_label'])}</span> {esc(ui['test_note'])}</p>"
                if s["test"] else "")
        header = self.masthead(name, ui["setting_subtitle"], ui["brand"]) + note
        main = (f"<div class='lead'>{lead}</div>" if lead else "") + "\n".join(out)
        topbar = (f"<div class='links'><a href='{root}'>{esc(ui['back_home'])}</a>"
                  f"<a class='rules' href='{root}#play'>{esc(ui['rules_link'])}</a></div>")
        data = None
        if creation:
            keys = ["to_choose", "sheet_copied", "sheet_copy_failed"]
            data = {"ui": {k: ui[k] for k in keys},
                    "creation": creation.data(f"rnp-sheet-{s['code']}")}
        extra_css = palette_css(read_palette(s["theme"]))
        return self.shell(L, root, f"{name} · {ui['brand']}", topbar, header, main, extra_css, data)

    # ---------- scrittura

    def write(self, rel, text):
        path = self.out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf8", newline="\n")
        print("scritto", rel)

    def build(self):
        self.write("assets/site.css", palette_css(self.palette) + "\n" + self.css)
        self.write("assets/site.js", self.js)
        self.write(".nojekyll", "")
        for lc in self.config["languages"]:
            L = self.lang(lc)
            base = "" if lc == self.config["default_language"] else f"{lc}/"
            self.write(f"{base}index.html", self.home(L))
            for s in self.settings:
                self.write(f"{base}{s['code']}/index.html", self.setting_page(L, s))


def main():
    ap = argparse.ArgumentParser(description="Genera il sito Roll&Play in docs/.")
    ap.add_argument("--vault", required=True, help="cartella Roll&Play del vault")
    ap.add_argument("--out", default=str(HERE.parent / "docs"), help="cartella di uscita (default: docs/)")
    ap.add_argument("--manual", action="append", default=[], metavar="SETTING=FILE",
                    help="usa FILE come MANUAL del setting (materiale di prova)")
    a = ap.parse_args()
    overrides = dict(x.split("=", 1) for x in a.manual)
    Site(a.vault, a.out, overrides).build()


if __name__ == "__main__":
    main()
