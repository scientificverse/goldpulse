#!/usr/bin/env python3
"""Builds the static gold and silver rate website into ./site. Standard library only.

  python build.py

Reads config.json (site name, cities), data/rates.json (prices) and content/
(guides), and writes: home, a gold page and a silver page per city, the silver
home, the guides hub and each guide, two tools, about/disclaimer/privacy/terms/
contact, 404, sitemap.xml and robots.txt. Upload the ./site folder to any static host.
"""
import datetime as dt
import hashlib
import html
import json
import math
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "site"
STATIC = ROOT / "static"
CONTENT = ROOT / "content"
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
RATES = json.loads((ROOT / "data" / "rates.json").read_text(encoding="utf-8"))
GUIDES = json.loads((CONTENT / "guides.json").read_text(encoding="utf-8"))
GUIDES_UPDATED = "2026-10-31"

E = html.escape
SITE = CFG["site_name"]
BASE_URL = CFG["site_url"].rstrip("/")
GST = CFG["gst_percent"]
GOLD = [("k24", "24 Carat", "99.9% pure", "Coins and bars"),
        ("k22", "22 Carat", "91.6% pure", "Most jewellery"),
        ("k18", "18 Carat", "75% pure", "Diamond and stone jewellery")]
GOLD_WEIGHTS = [(1, "1 gram"), (8, "8 grams (1 pavan)"), (10, "10 grams"), (100, "100 grams")]
SILVER_WEIGHTS = [(1, "1 gram"), (10, "10 grams"), (100, "100 grams"), (500, "500 grams"), (1000, "1 kilogram")]
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
       "font-src 'self'; connect-src 'self'; base-uri 'self'; form-action 'none'; object-src 'none'")


# ---------- small formatting helpers ----------

def inr(n, dec=0):
    """Indian digit grouping: 1413808 -> 14,13,808 (dec = digits after the point)."""
    whole, _, frac = f"{abs(n):.{dec}f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups) + "," + tail
    return ("-" if n < 0 and float(f"{abs(n):.{dec}f}") else "") + whole + ("." + frac if dec else "")


def rupees(n, dec=0):
    return "₹" + inr(n, dec)


def long_date(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b %Y')}"


def short_date(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b')}"


def clock(hhmm):
    """"14:05" -> "2:05 PM"."""
    h, m = map(int, hhmm.split(":"))
    return f"{(h - 1) % 12 + 1}:{m:02d} {'AM' if h < 12 else 'PM'}"


def change(diff, big=False, dec=0):
    cls = "chg chg-big" if big else "chg"
    if round(diff, dec) > 0:
        return f'<span class="{cls} up"><span aria-hidden="true">▲</span><span class="sr">Up by</span> {rupees(diff, dec)}</span>'
    if round(diff, dec) < 0:
        return f'<span class="{cls} down"><span aria-hidden="true">▼</span><span class="sr">Down by</span> {rupees(-diff, dec)}</span>'
    return f'<span class="{cls} same">No change</span>'


def asset(name):
    """Asset URL with a content hash so browsers pick up new versions."""
    digest = hashlib.sha1((STATIC / name).read_bytes()).hexdigest()[:8]
    return f"assets/{name}?v={digest}"


def updated_text():
    stamp = dt.datetime.fromisoformat(RATES["updated"])
    return f"{stamp.day} {stamp.strftime('%b %Y')}, {clock(stamp.strftime('%H:%M'))} IST"


def times_text():
    """["10:00 AM", "2:00 PM", "6:00 PM"] -> "10:00 AM, 2:00 PM and 6:00 PM"."""
    t = CFG["update_times_ist"]
    return t[0] if len(t) == 1 else ", ".join(t[:-1]) + " and " + t[-1]


def times_word():
    return {1: "once", 2: "twice", 3: "three times"}.get(len(CFG["update_times_ist"]),
                                                         f"{len(CFG['update_times_ist'])} times")


# ---------- price data ----------

def gold_hist(slug):
    return [e for e in RATES["cities"].get(slug, []) if "k24" in e]


def silver_hist(slug):
    return [e for e in RATES["cities"].get(slug, []) if "s" in e]


def now_prev(hist):
    return hist[0], (hist[1] if len(hist) > 1 else hist[0])


def silver_g(e):
    return e["s"] / 1000


GOLD_CITIES = [c for c in CFG["cities"] if gold_hist(c["slug"])]
SILVER_CITIES = [c for c in CFG["cities"] if silver_hist(c["slug"])]
FEATURED = next((c for c in GOLD_CITIES if c["slug"] == CFG["featured_city"]),
                GOLD_CITIES[0] if GOLD_CITIES else None)
FEATURED_SILVER = next((c for c in SILVER_CITIES if c["slug"] == CFG["featured_city"]),
                       SILVER_CITIES[0] if SILVER_CITIES else None)
GOLD_COLS = [(name, (lambda k: lambda e: e[k])(k), 0) for k, name, *_ in GOLD]
SILVER_COLS = [("Silver 1 gram", silver_g, 2), ("Silver 1 kg", lambda e: e["s"], 0)]


def gold_url(c):
    return f"gold-rate-{c['slug']}.html"


def silver_url(c):
    return f"silver-rate-{c['slug']}.html"


GOLD_UNITS = [(1, "1 g", "gram"), (8, "8 g (1 pavan)", "8 grams (1 pavan)"), (10, "10 g", "10 grams"),
              (11.6638, "1 tola", "tola"), (100, "100 g", "100 grams"), (1000, "1 kg", "kg")]
SILVER_UNITS = [(1, "1 g", "gram"), (10, "10 g", "10 grams"), (100, "100 g", "100 grams"), (1000, "1 kg", "kg")]
EMBLEM = """<svg class="brand-emblem" viewBox="0 0 40 40" fill="none" aria-hidden="true">
<defs><linearGradient id="emb" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
<stop offset="0" stop-color="#fff3b0"/><stop offset=".35" stop-color="#fed053"/><stop offset=".7" stop-color="#d4af37"/><stop offset="1" stop-color="#8c6615"/></linearGradient></defs>
<circle cx="20" cy="20" r="18" stroke="url(#emb)" stroke-width="1.8" stroke-dasharray="2,3"/>
<polygon points="20,4 24,14 35,14 26,21 30,32 20,25 10,32 14,21 5,14 16,14" fill="url(#emb)" fill-opacity=".25" stroke="url(#emb)" stroke-width="1.5"/>
<circle cx="20" cy="20" r="6" fill="url(#emb)"/><circle cx="20" cy="20" r="2.5" fill="#0a0d14"/></svg>"""


UNIT = {"mult": 10, "label": "10 grams"}   # weight the current page's prices start in


def set_unit(mult, label):
    UNIT["mult"], UNIT["label"] = mult, label


def scaled(value, dec=0):
    """A price that the weight chips can rescale: data-g holds the value for 1 gram,
    the text shows it for the page's starting weight (UNIT)."""
    m = UNIT["mult"]
    return f'<span data-g="{value:.4f}" data-dec="{dec}">{rupees(value * m, dec if m == 1 else 0)}</span>'


def pct(diff, prev):
    return f' <span class="pct">({diff / prev * 100:+.2f}%)</span>' if prev else ""


def change_scaled(diff, prev, dec=0, big=True, show_pct=True):
    """Like change(), but the amount follows the weight chips and the % change is added."""
    cls = "chg chg-big" if big else "chg"
    if round(diff, dec) > 0:
        return (f'<span class="{cls} up"><span aria-hidden="true">▲</span><span class="sr">Up by</span> '
                f'{scaled(diff, dec)}{pct(diff, prev) if show_pct else ""}</span>')
    if round(diff, dec) < 0:
        return (f'<span class="{cls} down"><span aria-hidden="true">▼</span><span class="sr">Down by</span> '
                f'{scaled(-diff, dec)}{pct(diff, prev) if show_pct else ""}</span>')
    return f'<span class="{cls} same">No change</span>'


def unit_chips(units):
    btns = "".join(f'<button type="button" data-mult="{m}" data-label="{E(lbl)}" aria-pressed="{"true" if m == UNIT["mult"] else "false"}">{E(t)}</button>'
                   for m, t, lbl in units)
    return (f'<div class="units" role="group" aria-label="Show prices for this weight">'
            f'<span class="units-label">Price for</span><div class="chips">{btns}</div></div>')


def day_range(now, f, need):
    """Lowest and highest of today's updates, or None if there was only one."""
    vals = [f(u) for u in now.get("u", []) if need in u]
    return (min(vals), max(vals)) if len(vals) > 1 else None


GOLD_FN = {k: (lambda k: lambda e: e[k])(k) for k, *_ in GOLD}


# ---------- page shell ----------

PAGES = []   # every written page, for the sitemap


def ticker():
    items = []
    if FEATURED:
        now, prev = now_prev(gold_hist(FEATURED["slug"]))
        for k, label in (("k22", "22K Gold"), ("k24", "24K Gold")):
            items.append((gold_url(FEATURED), f"{FEATURED['name']} {label}", f"{rupees(now[k])}/g", now[k] - prev[k]))
    if FEATURED_SILVER:
        now, prev = now_prev(silver_hist(FEATURED_SILVER["slug"]))
        items.append((silver_url(FEATURED_SILVER), f"{FEATURED_SILVER['name']} Silver", f"{rupees(now['s'])}/kg",
                      now["s"] - prev["s"]))
    for c in [c for c in GOLD_CITIES if c is not FEATURED][:6]:
        now, prev = now_prev(gold_hist(c["slug"]))
        items.append((gold_url(c), f"{c['name']} 22K", f"{rupees(now['k22'])}/g", now["k22"] - prev["k22"]))
    lis = "".join(f'<li><a href="{u}"><span class="tk-name">{E(n)}</span> <span class="tk-val">{v}</span> {change(d)}</a></li>'
                  for u, n, v, d in items)
    # The list is repeated once (hidden from screen readers) so the strip can scroll in a seamless loop.
    copy = lis.replace('<a href=', '<a tabindex="-1" href=')
    return (f'<div class="ticker" role="region" aria-label="Today\'s prices"><div class="ticker-track">'
            f'<ul>{lis}</ul><ul aria-hidden="true">{copy}</ul></div></div>')


def footer_cols():
    gold = "".join(f'<li><a href="{gold_url(c)}">Gold rate in {E(c["name"])}</a></li>' for c in GOLD_CITIES[:6])
    silver = "".join(f'<li><a href="{silver_url(c)}">Silver rate in {E(c["name"])}</a></li>' for c in SILVER_CITIES[:6])
    guides = "".join(f'<li><a href="{g["slug"]}.html">{E(g["title"])}</a></li>' for g in GUIDES[:6])
    return f"""<div class="foot-cols">
  <div><h2>Gold rates</h2><ul>{gold}<li><a href="index.html#cities">All cities</a></li></ul></div>
  <div><h2>Silver rates</h2><ul>{silver}<li><a href="silver-rate-today.html#cities">All cities</a></li></ul></div>
  <div><h2>Guides</h2><ul>{guides}<li><a href="guides.html">All guides</a></li></ul></div>
  <div><h2>Tools &amp; site</h2><ul>
    <li><a href="gold-weight-converter.html">Gold weight converter</a></li>
    <li><a href="gold-purity-calculator.html">Gold purity calculator</a></li>
    <li><a href="about.html">About us</a></li><li><a href="contact.html">Contact</a></li>
  </ul></div>
</div>"""


def sidebar(section, path):
    """Left column: today's prices, cities, tools and guides, always in reach while scrolling."""
    def link(href, text, extra=""):
        cur = ' aria-current="page"' if href == path else ""
        return f'<li><a href="{href}"{cur}><span>{text}</span>{extra}</a></li>'

    boxes = []
    if FEATURED:
        n, p = now_prev(gold_hist(FEATURED["slug"]))
        rows = [("22K · 1 g", rupees(n["k22"]), change(n["k22"] - p["k22"])),
                ("24K · 1 g", rupees(n["k24"]), change(n["k24"] - p["k24"]))]
        if FEATURED_SILVER:
            sn, sp = now_prev(silver_hist(FEATURED_SILVER["slug"]))
            rows.append(("Silver · 1 kg", rupees(sn["s"]), change(sn["s"] - sp["s"])))
        dl = "".join(f'<div><dt>{k}</dt><dd><strong>{v}</strong> {d}</dd></div>' for k, v, d in rows)
        boxes.append(f'<section class="side-box side-today"><h2 class="side-title">Today in {E(FEATURED["name"])}</h2>'
                     f'<dl>{dl}</dl><a class="side-more" href="{gold_url(FEATURED)}">Full {E(FEATURED["name"])} page →</a></section>')
    silver_side = section == "silver"
    cities = SILVER_CITIES if silver_side else GOLD_CITIES
    items = []
    for c in cities:
        if silver_side:
            n, _ = now_prev(silver_hist(c["slug"]))
            items.append(link(silver_url(c), E(c["name"]), f'<span class="side-val">{rupees(n["s"])}</span>'))
        else:
            n, _ = now_prev(gold_hist(c["slug"]))
            items.append(link(gold_url(c), E(c["name"]), f'<span class="side-val">{rupees(n["k22"])}</span>'))
    head = "Silver rate by city · 1 kg" if silver_side else "Gold rate by city · 22K, 1 g"
    switch = (link("index.html", "Gold rates in all cities") if silver_side
              else link("silver-rate-today.html", "Silver rates in all cities"))
    boxes.append(f'<nav class="side-box" aria-label="{head}"><h2 class="side-title">{head}</h2>'
                 f'<ul class="side-list">{"".join(items)}</ul><ul class="side-list side-extra">{switch}</ul></nav>')
    tools = [("gold-weight-converter.html", "Gold weight converter"), ("gold-purity-calculator.html", "Gold purity calculator")]
    if FEATURED:
        tools.append((gold_url(FEATURED) + "#calculator", "Jewellery price calculator"))
    boxes.append('<nav class="side-box" aria-label="Tools"><h2 class="side-title">Tools</h2><ul class="side-list">'
                 + "".join(link(h, t) for h, t in tools) + "</ul></nav>")
    picks = [g for g in GUIDES if g["slug"] in ("gold-buying-checklist", "bis-hallmark-huid", "making-charges-and-wastage",
                                                 "gst-on-gold", "selling-old-gold")]
    boxes.append('<nav class="side-box" aria-label="Popular guides"><h2 class="side-title">Popular guides</h2><ul class="side-list">'
                 + "".join(link(f'{g["slug"]}.html', E(g["title"])) for g in picks)
                 + link("guides.html", f"All {len(GUIDES)} guides →") + "</ul></nav>")
    return "".join(boxes)


def ad_rail():
    """Right column kept free for one tall ad (300 × 600). It has a fixed size, so an ad
    loading in it can never push the page content around."""
    if not CFG.get("ad_placeholders", True):
        return '<div class="ad-slot ad-300x600"></div>'   # space stays reserved, nothing shown
    return ('<div class="ad-slot ad-300x600"><span class="ad-label">Advertisement</span>'
            '<span class="ad-holder">Ad space<br>300 × 600</span></div>')


def page(path, section, title, description, body):
    PAGES.append(path)
    canonical = BASE_URL + "/" + ("" if path == "index.html" else path)
    nav = [("index.html", "gold", "Gold rates"), ("silver-rate-today.html", "silver", "Silver rates"),
           ("guides.html", "guides", "Guides"), ("gold-weight-converter.html", "tools", "Tools"),
           ("about.html", "about", "About")]
    links = "".join(f'<a href="{h}"{" aria-current=page" if s == section else ""}>{t}</a>' for h, s, t in nav)
    sample = ""
    if RATES.get("sample"):
        sample = ('<p class="sample-note" role="note"><strong>Sample prices.</strong> '
                  'These numbers are made up to show how the site looks. '
                  'Real prices appear once the price feed is switched on.</p>')
    year = dt.date.today().year
    return f"""<!doctype html>
<html lang="en-IN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>{E(title)}</title>
<meta name="description" content="{E(description)}">
<link rel="canonical" href="{E(canonical)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{E(SITE)}">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(description)}">
<meta property="og:url" content="{E(canonical)}">
<meta name="color-scheme" content="light">
<meta name="theme-color" content="#faf7f2">
<link rel="icon" href="assets/favicon.svg" type="image/svg+xml">
<link rel="preload" href="assets/fonts/jakarta-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="assets/fonts/cinzel-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{asset('style.css')}">
<script src="{asset('app.js')}" defer></script>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<div class="market-bar">
  <div class="wrap market-in">
    {ticker()}
  </div>
</div>
<header class="top">
  <div class="wrap top-in">
    <a class="brand" href="index.html">{EMBLEM}<span class="brand-text"><span class="brand-name gold-text">{E(SITE)}</span><span class="brand-sub">India gold &amp; silver prices</span></span></a>
    <button class="menu-btn" id="menu-btn" type="button" aria-label="Menu" aria-expanded="false" aria-controls="main-nav"><span></span><span></span><span></span></button>
    <nav class="nav" id="main-nav" aria-label="Main">{links}</nav>
  </div>
</header>
<div class="layout">
<aside class="side-left" aria-label="Quick links">{sidebar(section, path)}</aside>
<main id="main">
{sample}
{body}
</main>
<aside class="side-right" aria-label="Advertisement">{ad_rail()}</aside>
</div>
<footer class="foot">
  <div class="wrap">
    {footer_cols()}
    <p class="foot-note">Prices are a guide and do not include GST ({GST}%) or making charges.
    Your jeweller's price can be different. Nothing on this site is financial advice.</p>
    <nav class="foot-links" aria-label="Footer">
      <a href="about.html">About</a><a href="disclaimer.html">Disclaimer</a><a href="privacy.html">Privacy</a>
      <a href="terms.html">Terms</a><a href="contact.html">Contact</a>
    </nav>
    <p class="foot-copy">© {year} {E(SITE)}</p>
  </div>
</footer>
</body>
</html>
"""


def write(path, text):
    target = OUT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


# ---------- building blocks ----------

def card(cls, title, purity, tag, value, diff, prev, stats, btn, hl=2, dec=0, star="", tag_cls=""):
    """One Swarna-style price card. value/diff/prev are for 1 gram; the weight chips rescale them."""
    stat_html = "".join(f'<div><dt>{k}</dt><dd{" class=hl" if h else ""}>{v}</dd></div>' for k, v, h in stats)
    star_html = f' <span class="star">★ {star}</span>' if star else ""
    href, label = btn
    return f"""<article class="card {cls}">
  <div class="card-top"><div><h{hl} class="card-title">{title}{star_html}</h{hl}><span class="card-purity">{purity}</span></div><span class="tag {tag_cls}">{tag}</span></div>
  <p class="card-price"><span class="amt">{scaled(value, dec)}</span><span class="per" data-per>/ {UNIT["label"]}</span></p>
  <p class="card-chg">{change_scaled(diff, prev, dec)} <span class="vs">since yesterday</span></p>
  <dl class="card-stats">{stat_html}</dl>
  <a class="card-btn" href="{href}">{label}</a>
</article>"""


GOLD_CARD = {
    "k24": ("Coins &amp; bars", "", "", "Coins, bars, savings"),
    "k22": ("BIS 916", "tag-bis", "Most popular", "Wedding &amp; daily jewellery"),
    "k18": ("Diamond setting", "", "", "Diamond &amp; stone jewellery"),
}


def gold_card(slug, k, hl, calc_href):
    now, prev = now_prev(gold_hist(slug))
    name, purity = next((n, p) for kk, n, p, _ in GOLD if kk == k)
    tag, tag_cls, star, best = GOLD_CARD[k]
    rng = day_range(now, GOLD_FN[k], "k24")
    stats = []
    if rng:
        stats.append(("Today's range", f"{scaled(rng[0])} – {scaled(rng[1])}", False))
    stats.append(("Best for", best, False))
    return card(f"card-{k}", name.replace(" Carat", " Karat"), purity, tag, now[k], now[k] - prev[k], prev[k], stats,
                (calc_href, f"Work out {name.split()[0]}K jewellery price"), hl, star=star, tag_cls=tag_cls)


def silver_card(slug, hl, href, label, sterling=False):
    now, prev = now_prev(silver_hist(slug))
    f = 0.925 if sterling else 1
    rng = day_range(now, lambda u: u["s"] / 1000 * f, "s")
    stats = []
    if rng:
        stats.append(("Today's range", f"{scaled(rng[0], 2)} – {scaled(rng[1], 2)}", False))
    stats.append(("1 kg", rupees(now["s"] * f), True))
    stats.append(("Best for", "Jewellery, anklets, gifts" if sterling else "Coins, bars, pooja items", False))
    return card("card-silver", "Sterling silver" if sterling else "Silver", "92.5% (925)" if sterling else "99.9% fine (999)",
                "Jewellery grade" if sterling else "Chandi", silver_g(now) * f, (silver_g(now) - silver_g(prev)) * f,
                silver_g(prev) * f, stats, (href, label), hl, dec=2)


def gold_cards(slug, hl=2, calc_href="#calculator"):
    return '<div class="cards">' + "".join(gold_card(slug, k, hl, calc_href) for k, *_ in GOLD) + "</div>"


def silver_cards(slug, hl=2):
    return ('<div class="cards cards-2">'
            + silver_card(slug, hl, "#calculator", "Work out silver price")
            + silver_card(slug, hl, "#calculator", "Work out sterling silver price", sterling=True)
            + "</div>")


def table(caption, aria, head, rows, table_id=""):
    ths = "".join(f'<th scope="col">{h}</th>' for h in head)
    tid = f' id="{table_id}"' if table_id else ""
    return f"""<div class="table-scroll" tabindex="0" role="region" aria-label="{E(aria)}">
<table class="rates"{tid}>
<caption class="sr">{caption}</caption>
<thead><tr>{ths}</tr></thead>
<tbody>{"".join(rows)}</tbody>
</table></div>"""


def cell(value, diff, dec=0, first=""):
    tail = first if diff is None else change(diff, dec=dec)
    return f'<td><span class="num">{rupees(value, dec)}</span>{tail}</td>'


def history_rows(hist, cols, days=10):
    rows = []
    for i, e in enumerate(hist[:days]):
        prev = hist[i + 1] if i + 1 < len(hist) else e
        cells = "".join(cell(f(e), f(e) - f(prev), dec) for _, f, dec in cols)
        rows.append(f'<tr><th scope="row"><time datetime="{e["d"]}">{long_date(e["d"])}</time></th>{cells}</tr>')
    return rows


def updates_block(city, hist, cols, metal, need):
    """Today's updates table, shown only when today has two or more updates with this metal's price."""
    now = hist[0]
    ups = [u for u in now.get("u", []) if need in u]
    if len(ups) < 2:
        return ""
    first = '<span class="chg same">First price today</span>'
    rows = []
    for i, u in enumerate(ups):
        prev = ups[i - 1] if i else None
        cells = "".join(cell(f(u), f(u) - f(prev) if prev else None, dec, first) for _, f, dec in cols)
        rows.append(f'<tr><th scope="row"><time datetime="{now["d"]}T{u["t"]}">{clock(u["t"])}</time></th>{cells}</tr>')
    return f"""<section class="block" id="today-updates">
  <h2>Today's {metal.lower()} price updates in {E(city['name'])}</h2>
  <p class="lede">The price is checked {times_word()} a day. The latest one is the price shown at the top.</p>
  {table(f"{metal} price in {E(city['name'])} at each update on {long_date(now['d'])}", "Today's price updates",
         ["Time"] + [n for n, *_ in cols], rows)}
</section>"""


def nice_step(span):
    raw = max(span, 1) / 4
    for step in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000, 20000, 25000, 50000):
        if step >= raw:
            return step
    return 10 ** math.ceil(math.log10(raw))


def chart_svg(pts, label, gid):
    """pts: [(iso date, value)] oldest first -> an SVG line chart with hover titles."""
    vals = [v for _, v in pts]
    step = nice_step(max(vals) - min(vals))
    lo = math.floor(min(vals) / step) * step
    hi = math.ceil(max(vals) / step) * step
    if hi == lo:
        hi += step
    W, H, L, R, T, B = 640, 260, 92, 18, 16, 34
    n = len(pts)

    def x(i):
        return L + i * (W - L - R) / (n - 1)

    def y(v):
        return T + (hi - v) / (hi - lo) * (H - T - B)

    grid = []
    v = lo
    while v <= hi:
        grid.append(f'<line class="grid" x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
                    f'<text class="ylab" x="{L - 8}" y="{y(v) + 4:.1f}">{rupees(v)}</text>')
        v += step
    if n <= 7:
        marks = [(i, "middle") for i in range(n)]
        marks[0], marks[-1] = (0, "start"), (n - 1, "end")
    else:
        marks = [(0, "start"), (n // 2, "middle"), (n - 1, "end")]
    xlabels = "".join(f'<text class="xlab" x="{x(i):.1f}" y="{H - 6}" text-anchor="{a}">{short_date(pts[i][0])}</text>'
                      for i, a in marks)
    line = " ".join(f"{'M' if i == 0 else 'L'}{x(i):.1f} {y(v):.1f}" for i, (_, v) in enumerate(pts))
    area = f"{line} L{x(n - 1):.1f} {H - B} L{x(0):.1f} {H - B} Z"
    dots = "".join(f'<circle class="pt" cx="{x(i):.1f}" cy="{y(v):.1f}" r="3.5"/>'
                   for i, (_, v) in enumerate(pts)) if n <= 10 else ""
    hits = "".join(f'<circle class="hit" cx="{x(i):.1f}" cy="{y(v):.1f}" r="8"><title>{long_date(d)}: {rupees(v)}</title></circle>'
                   for i, (d, v) in enumerate(pts))
    summary = (f"{label} over the last {n} days, from {rupees(pts[0][1])} on {long_date(pts[0][0])} "
               f"to {rupees(pts[-1][1])} on {long_date(pts[-1][0])}.")
    return f"""<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="{E(summary)}">
<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="stop-a"/><stop offset="1" class="stop-b"/></linearGradient></defs>
{"".join(grid)}
<path class="area" d="{area}" fill="url(#{gid})"/>
<path class="line" d="{line}"/>
{dots}
<circle class="dot" cx="{x(n - 1):.1f}" cy="{y(pts[-1][1]):.1f}" r="4.5"/>
{hits}
{xlabels}
</svg>"""


def trend_block(series):
    """series: [(key, label, [(iso, value)] newest first)]. Builds 7/30/90-day panels per series."""
    n = len(series[0][2])
    if n < 2:
        return '<p class="muted">The chart appears once there are two days of prices.</p>'
    ranges = [d for d in (7, 30, 90) if d <= n] or [n]
    default = 30 if 30 in ranges else ranges[-1]
    panels = []
    for si, (key, label, pts) in enumerate(series):
        for days in ranges:
            part = pts[:days]
            high = max(part, key=lambda p: p[1])
            low = min(part, key=lambda p: p[1])
            hidden = "" if (si, days) == (0, default) else " hidden"
            panels.append(f"""<div class="panel" data-key="{key}" data-days="{days}"{hidden}>
<dl class="stats">
  <div><dt>Highest</dt><dd>{rupees(high[1])}<small>{long_date(high[0])}</small></dd></div>
  <div><dt>Lowest</dt><dd>{rupees(low[1])}<small>{long_date(low[0])}</small></dd></div>
  <div><dt>Change in {len(part)} days</dt><dd>{change(part[0][1] - part[-1][1])}</dd></div>
</dl>
{chart_svg(list(reversed(part)), label, f"g-{key}-{days}")}
</div>""")
    keys = ""
    if len(series) > 1:
        kb = "".join(f'<button type="button" data-key="{k}" aria-pressed="{"true" if i == 0 else "false"}">{E(lbl.replace(" gold", ""))}</button>'
                     for i, (k, lbl, _) in enumerate(series))
        keys = f'<div class="seg" role="group" aria-label="Gold type">{kb}</div>'
    rb = "".join(f'<button type="button" data-days="{d}" aria-pressed="{"true" if d == default else "false"}">{d} days</button>'
                 for d in ranges)
    return f"""<div class="trend">
<div class="toggles">{keys}<div class="seg" role="group" aria-label="Time range">{rb}</div></div>
{"".join(panels)}
</div>"""


def calculator(options, units, weight, making, note, place, date):
    """Swarna-style calculator: form on the left, a bill-style receipt on the right.
    options: [(short name, full name, rate per gram, selected)]."""
    pills = "".join(f'<label><input type="radio" name="c-rate" value="{rate:.2f}" data-name="{E(full)}"{" checked" if sel else ""}>'
                    f'<span>{E(short)}</span></label>' for short, full, rate, sel in options)
    rates = "".join(f'<div><dt>{E(full)}</dt><dd>{rupees(rate, 2 if rate < 1000 else 0)} / g</dd></div>' for _, full, rate, _ in options)
    unit_opts = "".join(f'<option value="{f}">{E(u)}</option>' for u, f in units)
    return f"""<form class="calc" id="calc-form" data-gst="{GST}" data-place="{E(place)}" data-date="{E(date)}" data-site="{E(SITE)}" novalidate>
<div class="calc-left">
  <fieldset class="pills"><legend>Metal and purity</legend>{pills}</fieldset>
  <div class="row-2">
    <label class="field"><span class="field-label">Weight</span><input id="c-weight" type="number" inputmode="decimal" min="0" step="0.01" value="{weight}"></label>
    <label class="field"><span class="field-label">Unit</span><select id="c-unit">{unit_opts}</select></label>
  </div>
  <div class="field">
    <div class="slider-head"><label class="field-label" for="c-making">Making charge</label><output class="slider-val" id="c-making-val" for="c-making">{making}%</output></div>
    <input id="c-making" type="range" min="0" max="30" step="0.5" value="{making}">
    <span class="hint">{note}</span>
  </div>
  <label class="check"><input id="c-gst" type="checkbox" checked> Add GST ({GST}%) on metal value + making charge</label>
  <dl class="out-grid">{rates}</dl>
</div>
<div class="receipt" aria-live="polite">
  <div class="receipt-head"><span class="receipt-brand">Price estimate</span><span class="receipt-badge" id="o-type">—</span></div>
  <dl>
    <div><dt>Weight</dt><dd id="o-weight">—</dd></div>
    <div><dt>Metal value</dt><dd id="o-gold">—</dd></div>
    <div><dt>Making charge</dt><dd id="o-making">—</dd></div>
    <div><dt>GST</dt><dd id="o-gst">—</dd></div>
    <div class="total"><dt>Total you may pay</dt><dd id="o-total">—</dd></div>
  </dl>
  <button type="button" class="btn-gold" id="c-copy">Copy this estimate</button>
  <p class="hint">Rates for {E(place)} on {E(date)}. A guide only; your shop's bill may differ.</p>
  <noscript><p class="hint">Turn on JavaScript to use the calculator.</p></noscript>
</div>
</form>"""


def faq(items):
    return "".join(f'<details class="faq"><summary>{E(q)}</summary><div>{a}</div></details>' for q, a in items)


def city_card(c, rows):
    # In the small cards "No change" becomes a dash (screen readers still hear "No change").
    row_html = "".join(f'<div><span>{k}</span><strong>{v}</strong>'
                       f'{d.replace(">No change<", "><span aria-hidden=true>–</span><span class=sr>No change</span><")}</div>'
                       for k, v, d in rows)
    market = f'<span class="city-market">{E(c["market"])}</span>' if c.get("market") else ""
    return (f'<a class="city" href="{gold_url(c)}" data-name="{E(c["name"].lower())} {E(c["state"].lower())} {E(c.get("market", "").lower())}">'
            f'<span class="city-name">{E(c["name"])}</span>{market}<span class="city-rows">{row_html}</span></a>')


def city_grid(cities, metal, skip=None, grid_id=""):
    cells = []
    for c in cities:
        if c["slug"] == skip:
            continue
        rows = []
        if metal in ("gold", "both"):
            n, p = now_prev(gold_hist(c["slug"]))
            rows += [("22K", scaled(n["k22"]), change_scaled(n["k22"] - p["k22"], p["k22"], big=False, show_pct=False)),
                     ("24K", scaled(n["k24"]), change_scaled(n["k24"] - p["k24"], p["k24"], big=False, show_pct=False))]
        if metal in ("silver", "both") and silver_hist(c["slug"]):
            n, p = now_prev(silver_hist(c["slug"]))
            rows.append(("Silver", scaled(silver_g(n), 2),
                         change_scaled(silver_g(n) - silver_g(p), silver_g(p), dec=2, big=False, show_pct=False)))
        html_ = city_card(c, rows)
        if metal == "silver":
            html_ = html_.replace(f'href="{gold_url(c)}"', f'href="{silver_url(c)}"', 1)
        cells.append(html_)
    gid = f' id="{grid_id}"' if grid_id else ""
    return '<div class="city-grid"' + gid + '>' + "".join(cells) + "</div>"


def guide_cards(guides):
    return '<div class="guide-grid">' + "".join(
        f'<a class="guide-card" href="{g["slug"]}.html"><span class="guide-topic">{E(g["topic"])}</span>'
        f'<span class="guide-title">{E(g["title"])}</span><span class="guide-desc">{E(g["description"])}</span></a>'
        for g in guides) + "</div>"


def guides_about(*words):
    """Guides whose slug contains any of the words, for 'helpful guides' sections."""
    return [g for g in GUIDES if any(w in g["slug"] for w in words)]


def crumbs(*parts):
    items = []
    for href, label in parts[:-1]:
        items.append(f'<a href="{href}">{E(label)}</a><span aria-hidden="true">›</span>')
    items.append(f'<span aria-current="page">{E(parts[-1][1])}</span>')
    return f'<nav class="crumbs" aria-label="Breadcrumb">{"".join(items)}</nav>'


def search_head(h2_id, heading, tag=""):
    tag_html = f'<span class="section-tag">{tag}</span>' if tag else ""
    return f"""<div class="block-head">
    <div>{tag_html}<h2 id="{h2_id}">{heading}</h2></div>
    <label class="search"><span class="sr">Find your city</span><input id="city-search" type="search" placeholder="Find your city or market" autocomplete="off"></label>
  </div>"""


# ---------- gold pages ----------

def gold_city_page(city):
    set_unit(10, "10 grams")
    slug, name = city["slug"], city["name"]
    hist = gold_hist(slug)
    now, prev = now_prev(hist)
    date = long_date(now["d"])
    last_at = f", updated {clock(now['u'][-1]['t'])}" if now.get("u") else ""
    market_part = f" · {E(city['market'])}" if city.get("market") else ""
    title = f"Gold Rate Today in {name} ({date}) – 22K & 24K Price | {SITE}"
    desc = (f"Gold rate in {name} today, {date}: 22 carat {rupees(now['k22'])} and 24 carat "
            f"{rupees(now['k24'])} per gram. Price by weight, last 10 days, 7 and 30-day chart and calculator.")
    silver_box = ""
    if silver_hist(slug):
        s_now, s_prev = now_prev(silver_hist(slug))
        silver_box = (f'<p class="side-note">Silver in {E(name)} today: <strong>{rupees(silver_g(s_now), 2)}/g</strong> · '
                      f'<strong>{rupees(s_now["s"])}/kg</strong> {change(s_now["s"] - s_prev["s"])} '
                      f'<a href="{silver_url(city)}">Silver rate in {E(name)} →</a></p>')
    questions = [
        ("What is the difference between 24, 22 and 18 carat gold?",
         "<p>24 carat is almost pure gold (99.9%). It is soft, so it is used for coins and bars. "
         "22 carat has 91.6% gold mixed with a little copper or silver to make it strong, so most jewellery is 22 carat. "
         '18 carat has 75% gold and is used for diamond and stone jewellery. <a href="24k-22k-18k-gold-difference.html">Read the full guide</a>.</p>'),
        ("How many grams is one pavan (sovereign)?",
         f"<p>One pavan is 8 grams. Today one pavan of 22 carat gold in {E(name)} costs about {rupees(now['k22'] * 8)}, "
         'before GST and making charges. See the <a href="gold-weight-converter.html">gold weight converter</a>.</p>'),
        ("Why is the price at the shop higher than this?",
         f"<p>Shops add a making charge for the work on the jewellery, and the government adds {GST}% GST. "
         'Some shops also charge for wastage. Use the calculator above, or read <a href="making-charges-and-wastage.html">making charges explained</a>.</p>'),
        ("When is this rate updated?",
         f"<p>{times_word().capitalize()} a day, around {E(times_text())} India time. "
         f"This page was last updated on {updated_text()}.</p>"),
        ("How do I know my gold is real?",
         '<p>Look for the BIS hallmark with the purity (for example 22K916) and a 6-character HUID, and check the HUID '
         'on the BIS Care app. <a href="bis-hallmark-huid.html">How to check a hallmark</a>.</p>'),
    ]
    options = [(f"{n.split()[0]}K", f"{n} gold", now[k], k == "k22") for k, n, *_ in GOLD]
    if silver_hist(slug):
        options.append(("Silver 999", "Fine silver 999", silver_g(silver_hist(slug)[0]), False))
    calc = calculator(options, [("grams", 1), ("pavan (8 g)", 8), ("tola (11.66 g)", 11.6638)], 8,
                      CFG["default_making_percent"],
                      "Usually 8% to 25%, depending on the design. Ask your jeweller.", name, date)
    weight_rows = []
    for grams, label in GOLD_WEIGHTS:
        cells = "".join(cell(now[k] * grams, (now[k] - prev[k]) * grams) for k, *_ in GOLD)
        weight_rows.append(f'<tr><th scope="row">{label}</th>{cells}</tr>')
    body = f"""{crumbs(("index.html", "Gold rates"), ("", name))}
<header class="top-head">
  <div>
    <h1>Gold Rate Today in {E(name)}</h1>
    <p class="meta"><time datetime="{now['d']}">{date}</time>{last_at}{market_part} · Without GST</p>
  </div>
  {unit_chips(GOLD_UNITS)}
</header>
<section aria-label="Today's gold price">{gold_cards(slug)}</section>
{silver_box}
{updates_block(city, hist, GOLD_COLS, "Gold", "k24")}

<section class="block" id="by-weight">
  <h2>Gold price in {E(name)} by weight</h2>
  {table(f"Gold price in {E(name)} by weight on {date}", "Gold price by weight",
         ["Weight", "24 Carat", "22 Carat", "18 Carat"], weight_rows)}
</section>

<section class="block" id="trend">
  <h2>Gold price trend in {E(name)}</h2>
  {trend_block([("k22", "22 Carat gold", [(e["d"], e["k22"]) for e in hist]),
                ("k24", "24 Carat gold", [(e["d"], e["k24"]) for e in hist])])}
</section>

<section class="block" id="history">
  <h2>Gold rate in {E(name)}: last 10 days</h2>
  {table(f"Gold price for 1 gram in {E(name)}, last 10 days", "Gold price in the last 10 days",
         ["Date", "24 Carat", "22 Carat", "18 Carat"], history_rows(hist, GOLD_COLS))}
</section>

<section class="block" id="calculator">
  <span class="section-tag">Calculator</span>
  <h2>Gold jewellery price calculator</h2>
  <p class="lede">Find out what a piece of jewellery may cost with today's {E(name)} rate.</p>
  {calc}
</section>

<section class="block" id="faq">
  <h2>Common questions</h2>
  {faq(questions)}
</section>

<section class="block">
  <h2>Helpful guides</h2>
  {guide_cards(guides_about("checklist", "hallmark", "making-charges"))}
</section>

<section class="block" id="cities">
  <h2>Gold rate in other cities</h2>
  <p class="unit-note">Prices for <span data-unit>{UNIT["label"]}</span>, as picked at the top.</p>
  {city_grid(GOLD_CITIES, "gold", skip=slug)}
</section>"""
    write(gold_url(city), page(gold_url(city), "gold", title, desc, body))


def insights():
    return """<section class="block" aria-labelledby="bis-h">
  <span class="section-tag">Buy with confidence</span>
  <h2 id="bis-h">BIS hallmark &amp; purity checks</h2>
  <div class="insights">
    <article class="insight"><span class="insight-icon">3</span><h3>The 3 hallmark marks</h3>
      <ol><li>The BIS logo</li><li>Purity grade, like <strong>22K916</strong> or <strong>18K750</strong></li><li>A 6-character <strong>HUID</strong> code</li></ol>
      <a href="bis-hallmark-huid.html">How to read a hallmark →</a></article>
    <article class="insight"><span class="insight-icon">✓</span><h3>Check the HUID on your phone</h3>
      <p>Open the free BIS Care app, choose "Verify HUID" and type the 6-character code. It shows the item type, purity and the jeweller.</p>
      <a href="testing-gold-purity.html">Ways to test gold purity →</a></article>
    <article class="insight"><span class="insight-icon">₹</span><h3>Exchanging old gold</h3>
      <p>Shops pay for the pure gold inside, not the making charges you paid. Hallmarked gold usually gets the best value.</p>
      <a href="selling-old-gold.html">Selling or exchanging old gold →</a></article>
  </div>
</section>"""


def home_page():
    set_unit(10, "10 grams")
    feat = FEATURED
    now, _ = now_prev(gold_hist(feat["slug"]))
    date = long_date(now["d"])
    last_at = f"Updated {clock(now['u'][-1]['t'])}" if now.get("u") else f"Updated {date}"
    cards = "".join(gold_card(feat["slug"], k, 3, gold_url(feat) + "#calculator") for k, *_ in GOLD)
    if FEATURED_SILVER:
        cards += silver_card(FEATURED_SILVER["slug"], 3, silver_url(FEATURED_SILVER), "See silver rate")
    title = f"Gold Rate Today ({date}) – 22K, 24K Gold & Silver Price in India | {SITE}"
    desc = (f"Today's gold and silver rate in {len(GOLD_CITIES)} Indian cities, {date}. {feat['name']}: 22 carat "
            f"{rupees(now['k22'])}, 24 carat {rupees(now['k24'])} per gram. Updated {times_word()} a day.")
    questions = [
        ("Where do these prices come from?",
         "<p>We start from the world gold and silver price in rupees and add import duty and the usual local premium. "
         "22 carat is worked out as 22/24 of the 24 carat price, and 18 carat as 18/24. "
         '<a href="how-gold-rate-is-decided-in-india.html">How the gold rate is decided</a>.</p>'),
        ("Is this the exact price at my jeweller?",
         f"<p>No. It is a guide. Shops add making charges and {GST}% GST, and each shop sets its own rate.</p>"),
        ("How often is it updated?",
         f"<p>{times_word().capitalize()} a day, around {E(times_text())} India time. Last update: {updated_text()}.</p>"),
    ]
    body = f"""<header class="top-head">
  <div>
    <span class="section-tag">{E(feat['name'])} · {date} · {last_at}</span>
    <h1>Gold Rate <span class="gold-text">Today</span></h1>
  </div>
  {unit_chips(GOLD_UNITS)}
</header>

<section aria-label="Today's gold and silver price in {E(feat['name'])}">
  <div class="cards cards-4">{cards}</div>
  <p class="ref-note">Rates are for reference and don't include {GST}% GST or making charges; check with your jeweller before buying.
  <a href="{gold_url(feat)}">Full {E(feat['name'])} page →</a></p>
</section>

<section class="block intro" aria-labelledby="about-h">
  <h2 id="about-h">Today's gold and silver price, city by city</h2>
  <p class="lede">24K, 22K and 18K gold and fine silver for {len(GOLD_CITIES)} Indian cities, updated {times_word()} a day
  (around {E(times_text())} India time). Every city page has the price by weight, today's updates, 7, 30 and 90-day charts,
  the last 10 days and a jewellery calculator with {GST}% GST. Last update: {updated_text()}.</p>
</section>

<section class="block" id="cities" aria-labelledby="cities-h">
  {search_head("cities-h", "Gold &amp; silver rate in all cities", "Cities &amp; markets")}
  <p class="unit-note">Prices for <span data-unit>{UNIT["label"]}</span>, as picked at the top.</p>
  {city_grid(GOLD_CITIES, "both", grid_id="city-list")}
  <p class="muted" id="no-city" hidden>No city found. Try another name.</p>
</section>

{insights()}

<section class="block">
  <div class="block-head"><div><span class="section-tag">Learn</span><h2>Guides for gold buyers</h2></div><a class="more" href="guides.html">All {len(GUIDES)} guides →</a></div>
  {guide_cards(GUIDES[:6])}
</section>

<section class="block">
  <span class="section-tag">Free tools</span>
  <h2>Converters &amp; calculators</h2>
  <div class="guide-grid">
    <a class="guide-card" href="gold-weight-converter.html"><span class="guide-topic">Tool</span><span class="guide-title">Gold weight converter</span><span class="guide-desc">Grams, pavan, tola and ounce, with today's price.</span></a>
    <a class="guide-card" href="gold-purity-calculator.html"><span class="guide-topic">Tool</span><span class="guide-title">Gold purity calculator</span><span class="guide-desc">How much pure gold is in your jewellery, and what it is worth.</span></a>
    <a class="guide-card" href="{gold_url(feat)}#calculator"><span class="guide-topic">Tool</span><span class="guide-title">Jewellery price calculator</span><span class="guide-desc">Gold value + making charge + {GST}% GST, as a bill you can copy.</span></a>
  </div>
</section>

<section class="block">
  <h2>Good to know</h2>
  {faq(questions)}
</section>"""
    write("index.html", page("index.html", "gold", title, desc, body))


# ---------- silver pages ----------

def silver_city_page(city):
    set_unit(1000, "kg")
    slug, name = city["slug"], city["name"]
    hist = silver_hist(slug)
    now, prev = now_prev(hist)
    date = long_date(now["d"])
    last_at = f", updated {clock(now['u'][-1]['t'])}" if now.get("u") else ""
    title = f"Silver Rate Today in {name} ({date}) – Price per Gram & Kg | {SITE}"
    desc = (f"Silver rate in {name} today, {date}: {rupees(silver_g(now), 2)} per gram and {rupees(now['s'])} per kg. "
            "Price by weight, last 10 days, 7 and 30-day chart and calculator.")
    weight_rows = []
    for grams, label in SILVER_WEIGHTS:
        dec = 2 if grams < 100 else 0
        weight_rows.append(f'<tr><th scope="row">{label}</th>'
                           f'{cell(now["s"] * grams / 1000, (now["s"] - prev["s"]) * grams / 1000, dec)}</tr>')
    gold_box = ""
    if gold_hist(slug):
        g_now, g_prev = now_prev(gold_hist(slug))
        gold_box = (f'<p class="side-note">Gold in {E(name)} today: 22K <strong>{rupees(g_now["k22"])}/g</strong> '
                    f'{change(g_now["k22"] - g_prev["k22"])} · 24K <strong>{rupees(g_now["k24"])}/g</strong> '
                    f'<a href="{gold_url(city)}">Gold rate in {E(name)} →</a></p>')
    questions = [
        ("What purity is this silver rate for?",
         '<p>For fine silver, 99.9% pure (999). Sterling silver (925) and other mixes are worth less in proportion. '
         '<a href="silver-purity-999-925.html">Silver purity explained</a>.</p>'),
        ("Why is silver priced per kilogram?",
         f"<p>Silver costs much less per gram than gold, so traders quote it per kg. Divide by 1,000 for the gram price: "
         f"today {rupees(now['s'])} per kg is {rupees(silver_g(now), 2)} per gram.</p>"),
        ("Is GST included?",
         f"<p>No. {GST}% GST is added when you buy silver jewellery, coins or bars, along with any making charges.</p>"),
        ("Why does silver move more than gold?",
         "<p>Silver is also used in factories, for electronics and solar panels, so its price reacts to world industry "
         "as well as to the things that move gold.</p>"),
        ("When is this rate updated?",
         f"<p>{times_word().capitalize()} a day, around {E(times_text())} India time. Last update: {updated_text()}.</p>"),
    ]
    calc = calculator([("Fine 999", "Fine silver 999", silver_g(now), True),
                       ("Sterling 925", "Sterling silver 925", silver_g(now) * 0.925, False)],
                      [("grams", 1), ("kg", 1000)], 100, 8,
                      "Silver making charges vary a lot by design. Ask your shop.", name, date)
    body = f"""{crumbs(("silver-rate-today.html", "Silver rates"), ("", name))}
<header class="top-head">
  <div>
    <h1>Silver Rate Today in {E(name)}</h1>
    <p class="meta"><time datetime="{now['d']}">{date}</time>{last_at} · Fine silver (999) · Without GST</p>
  </div>
  {unit_chips(SILVER_UNITS)}
</header>
<section aria-label="Today's silver price">{silver_cards(slug)}</section>
{gold_box}
{updates_block(city, hist, SILVER_COLS, "Silver", "s")}

<section class="block" id="by-weight">
  <h2>Silver price in {E(name)} by weight</h2>
  {table(f"Silver price in {E(name)} by weight on {date}", "Silver price by weight", ["Weight", "Price"], weight_rows)}
</section>

<section class="block" id="trend">
  <h2>Silver price trend in {E(name)}</h2>
  {trend_block([("s", "Silver per kg", [(e["d"], e["s"]) for e in hist])])}
</section>

<section class="block" id="history">
  <h2>Silver rate in {E(name)}: last 10 days</h2>
  {table(f"Silver price in {E(name)}, last 10 days", "Silver price in the last 10 days",
         ["Date", "Silver 1 gram", "Silver 1 kg"], history_rows(hist, SILVER_COLS))}
</section>

<section class="block" id="calculator">
  <span class="section-tag">Calculator</span>
  <h2>Silver price calculator</h2>
  <p class="lede">Work out the price of a silver item with today's {E(name)} rate.</p>
  {calc}
</section>

<section class="block" id="faq">
  <h2>Common questions</h2>
  {faq(questions)}
</section>

<section class="block">
  <h2>Helpful guides</h2>
  {guide_cards(guides_about("silver", "caring", "gst"))}
</section>

<section class="block" id="cities">
  <h2>Silver rate in other cities</h2>
  <p class="unit-note">Prices for <span data-unit>{UNIT["label"]}</span>, as picked at the top.</p>
  {city_grid(SILVER_CITIES, "silver", skip=slug)}
</section>"""
    write(silver_url(city), page(silver_url(city), "silver", title, desc, body))


def silver_home():
    set_unit(1000, "kg")
    feat = FEATURED_SILVER
    now, _ = now_prev(silver_hist(feat["slug"]))
    date = long_date(now["d"])
    title = f"Silver Rate Today ({date}) – Price per Gram & Kg in Indian Cities | {SITE}"
    desc = (f"Today's silver rate in {len(SILVER_CITIES)} Indian cities, {date}. {feat['name']}: "
            f"{rupees(silver_g(now), 2)} per gram, {rupees(now['s'])} per kg. Updated {times_word()} a day.")
    body = f"""<header class="top-head">
  <div>
    <span class="section-tag">{E(feat['name'])} · {date} · fine 999 and sterling 925</span>
    <h1>Silver Rate <span class="gold-text">Today</span></h1>
  </div>
  {unit_chips(SILVER_UNITS)}
</header>

<section aria-label="Today's silver price in {E(feat['name'])}">
  <div class="cards cards-2">{silver_card(feat['slug'], 3, silver_url(feat) + "#calculator", "Work out silver price")}{silver_card(feat['slug'], 3, silver_url(feat) + "#calculator", "Work out sterling silver price", sterling=True)}</div>
  <p class="ref-note">Rates are for reference and don't include {GST}% GST or making charges; check with your shop before buying.
  <a href="{silver_url(feat)}">Full {E(feat['name'])} silver page →</a> · Last update {updated_text()}.</p>
</section>

<section class="block" id="cities" aria-labelledby="cities-h">
  {search_head("cities-h", "Silver rate in all cities", "Cities &amp; markets")}
  <p class="unit-note">Prices for <span data-unit>{UNIT["label"]}</span>, as picked at the top.</p>
  {city_grid(SILVER_CITIES, "silver", grid_id="city-list")}
  <p class="muted" id="no-city" hidden>No city found. Try another name.</p>
</section>

<section class="block">
  <span class="section-tag">Learn</span>
  <h2>Silver guides</h2>
  {guide_cards(guides_about("silver", "caring", "gst", "why-gold"))}
</section>"""
    write("silver-rate-today.html", page("silver-rate-today.html", "silver", title, desc, body))


# ---------- guides ----------

def guide_pages():
    by_topic = {}
    for g in GUIDES:
        by_topic.setdefault(g["topic"], []).append(g)
    sections = "".join(f'<section class="block"><h2>{E(t)}</h2>{guide_cards(gs)}</section>' for t, gs in by_topic.items())
    body = f"""{crumbs(("index.html", "Home"), ("", "Guides"))}
<header class="page-head">
  <h1>Gold and Silver Guides</h1>
  <p class="lede">Plain-language guides on how gold prices work, buying and selling jewellery safely, purity, hallmarks and taxes. Written for buyers, not traders.</p>
</header>
{sections}"""
    write("guides.html", page("guides.html", "guides", f"Gold and Silver Buying Guides | {SITE}",
                              "Simple guides on gold rates, hallmarks, making charges, GST, selling old gold and silver purity.", body))

    feat_box = ""
    if FEATURED:
        now, prev = now_prev(gold_hist(FEATURED["slug"]))
        feat_box = (f'<aside class="side-note" aria-label="Today\'s rate">Today in {E(FEATURED["name"])}: '
                    f'22K <strong>{rupees(now["k22"])}/g</strong> {change(now["k22"] - prev["k22"])} · '
                    f'24K <strong>{rupees(now["k24"])}/g</strong> '
                    f'<a href="{gold_url(FEATURED)}">See today\'s rate →</a></aside>')
    for i, g in enumerate(GUIDES):
        content = (CONTENT / "guides" / f"{g['slug']}.html").read_text(encoding="utf-8")
        words = len(re.sub(r"<[^>]+>", " ", content).split())
        minutes = max(1, round(words / 200))
        related = [x for x in GUIDES if x["topic"] == g["topic"] and x is not g]
        related += [x for x in GUIDES[i + 1:] + GUIDES[:i] if x not in related]
        updated = g.get("updated", GUIDES_UPDATED)
        body = f"""{crumbs(("index.html", "Home"), ("guides.html", "Guides"), ("", g["title"]))}
<header class="page-head">
  <p class="eyebrow">{E(g["topic"])}</p>
  <h1>{E(g["title"])}</h1>
  <p class="meta">Updated <time datetime="{updated}">{long_date(updated)}</time> · {minutes} min read · By the {E(SITE)} team</p>
</header>
{feat_box}
<article class="prose guide">
<p class="lede">{E(g["description"])}</p>
{content}
<p class="muted small">This guide is general information for buyers. Rules and tax rates can change; check with your jeweller,
bank or a qualified adviser before big decisions.</p>
</article>
<section class="block">
  <h2>Read next</h2>
  {guide_cards(related[:3])}
</section>"""
        write(f"{g['slug']}.html", page(f"{g['slug']}.html", "guides", f"{g['title']} | {SITE}", g["description"], body))


# ---------- tools ----------

UNITS = [("gram", "Grams", 1), ("pavan", "Pavan (sovereign)", 8), ("tola", "Tola", 11.6638),
         ("ounce", "Troy ounce", 31.1034768), ("kg", "Kilograms", 1000)]
CARATS = [(24, 999), (23, 958), (22, 916), (20, 833), (18, 750), (14, 585)]


def tools_pages():
    now, _ = now_prev(gold_hist(FEATURED["slug"]))
    name = FEATURED["name"]
    unit_opts = "".join(f'<option value="{f}"{" selected" if k == "pavan" else ""}>{E(lbl)}</option>' for k, lbl, f in UNITS)
    outs = "".join(f'<div><dt>{E(lbl)}</dt><dd data-factor="{f}">—</dd></div>' for k, lbl, f in UNITS)
    pavan_rows = [f'<tr><th scope="row">{p} pavan</th><td>{p * 8} g</td><td>{rupees(p * 8 * now["k22"])}</td><td>{rupees(p * 8 * now["k24"])}</td></tr>'
                  for p in (1, 2, 3, 5, 8, 10, 15, 20, 25, 50)]
    tola_rows = [f'<tr><th scope="row">{t} tola</th><td>{inr(t * 11.6638, 3)} g</td><td>{rupees(t * 11.6638 * now["k22"])}</td><td>{rupees(t * 11.6638 * now["k24"])}</td></tr>'
                 for t in (1, 2, 5, 10)]
    body = f"""{crumbs(("index.html", "Home"), ("", "Gold weight converter"))}
<header class="page-head">
  <h1>Gold Weight Converter</h1>
  <p class="lede">Convert between grams, pavan, tola, troy ounces and kilograms, and see what that much gold costs at today's {E(name)} rate.</p>
</header>
<form class="tool" id="wc-form" data-k22="{now['k22']}" data-k24="{now['k24']}" novalidate>
  <div class="row-2">
    <label>Amount <input id="wc-amount" type="number" inputmode="decimal" min="0" step="0.001" value="1"></label>
    <label>Unit <select id="wc-unit">{unit_opts}</select></label>
  </div>
  <dl class="out-grid" aria-live="polite">{outs}</dl>
  <dl class="out-grid" aria-live="polite">
    <div><dt>22K value in {E(name)}</dt><dd id="wc-v22">—</dd></div>
    <div class="total"><dt>24K value in {E(name)}</dt><dd id="wc-v24">—</dd></div>
  </dl>
  <noscript><p class="muted">Turn on JavaScript to use the converter. The tables below work without it.</p></noscript>
  <p class="muted small">Values are for the metal only, without making charges or GST.</p>
</form>

<section class="block">
  <h2>Pavan to grams, with today's price</h2>
  {table(f"Pavan to grams and price in {E(name)}", "Pavan to grams table", ["Pavan", "Grams", "22K price", "24K price"], pavan_rows)}
</section>
<section class="block">
  <h2>Tola to grams, with today's price</h2>
  {table(f"Tola to grams and price in {E(name)}", "Tola to grams table", ["Tola", "Grams", "22K price", "24K price"], tola_rows)}
</section>
<section class="block prose">
  <h2>The units in short</h2>
  <ul>
    <li><strong>1 pavan (sovereign) = 8 grams.</strong> Used in Tamil Nadu and Kerala.</li>
    <li><strong>1 tola = 11.6638 grams.</strong> Used in North and West India and the Gulf.</li>
    <li><strong>1 troy ounce = 31.1035 grams.</strong> The unit of the world gold price.</li>
  </ul>
  <p>More detail in <a href="gold-weight-units.html">Gram, pavan, tola and ounce explained</a>.</p>
</section>"""
    write("gold-weight-converter.html", page("gold-weight-converter.html", "tools",
          f"Gold Weight Converter – Gram, Pavan, Tola, Ounce | {SITE}",
          "Convert gold between grams, pavan, tola, troy ounces and kg, with today's 22K and 24K price.", body))

    carat_opts = "".join(f'<option value="{c}"{" selected" if c == 22 else ""}>{c} carat ({f / 10:.1f}%)</option>' for c, f in CARATS)
    carat_rows = [f'<tr><th scope="row">{c}K</th><td>{f / 10:.1f}%</td><td>{f}</td><td>{rupees(now["k24"] * c / 24)}</td></tr>'
                  for c, f in CARATS]
    body = f"""{crumbs(("index.html", "Home"), ("", "Gold purity calculator"))}
<header class="page-head">
  <h1>Gold Purity Calculator</h1>
  <p class="lede">Find out how much pure gold is in a piece of jewellery and what that gold is worth at today's {E(name)} rate.</p>
</header>
<form class="tool" id="pc-form" data-k24="{now['k24']}" novalidate>
  <div class="row-2">
    <label>Weight (grams) <input id="pc-weight" type="number" inputmode="decimal" min="0" step="0.001" value="10"></label>
    <label>Purity <select id="pc-carat">{carat_opts}</select></label>
  </div>
  <dl class="out-grid" aria-live="polite">
    <div><dt>Pure gold inside</dt><dd id="pc-pure">—</dd></div>
    <div><dt>Other metals</dt><dd id="pc-other">—</dd></div>
    <div class="total"><dt>Gold value today</dt><dd id="pc-value">—</dd></div>
  </dl>
  <noscript><p class="muted">Turn on JavaScript to use the calculator. The table below works without it.</p></noscript>
  <p class="muted small">Gold value = weight × carat ÷ 24 × today's 24K rate ({rupees(now['k24'])}/g). Shops may deduct a little when buying old gold.</p>
</form>

<section class="block">
  <h2>Carat, purity and today's price per gram</h2>
  {table(f"Gold purity and price per gram in {E(name)}", "Carat and purity table",
         ["Carat", "Gold in it", "Hallmark number", "Price per gram"], carat_rows)}
</section>
<section class="block prose">
  <h2>How it works</h2>
  <p>Carat tells you how many parts out of 24 are pure gold. 22 carat means 22 parts gold and 2 parts other metals,
  which is 91.6%. So a 10-gram 22K chain contains about 9.16 grams of pure gold.</p>
  <p>The hallmark number (like 916) is the same purity in parts per thousand. Look for it on the BIS hallmark:
  <a href="bis-hallmark-huid.html">how to read a hallmark</a>.</p>
  <p>When you sell old gold, shops pay for this pure gold content, not for the making charges.
  Read <a href="selling-old-gold.html">selling or exchanging old gold</a>.</p>
</section>"""
    write("gold-purity-calculator.html", page("gold-purity-calculator.html", "tools",
          f"Gold Purity Calculator – Carat to Pure Gold & Value | {SITE}",
          "Work out the pure gold content of 24K, 22K, 18K or 14K jewellery and its value at today's rate.", body))


# ---------- site pages ----------

def text_page(path, title, h1, inner, desc):
    body = f"""<header class="page-head"><h1>{E(h1)}</h1></header>
<article class="prose">{inner}</article>"""
    write(path, page(path, "about", f"{title} | {SITE}", desc, body))


def legal_pages():
    email = E(CFG["contact_email"])
    text_page("about.html", "About us", f"About {SITE}", f"""
<p>{E(SITE)} shows the price of gold and silver for {len(GOLD_CITIES)} Indian cities in one simple place: today's rate,
the price by weight, today's updates, the last 10 days and charts of how the price has moved. We also write plain-language
<a href="guides.html">guides</a> for people buying or selling jewellery, and offer free
<a href="gold-weight-converter.html">tools</a>.</p>
<h2>How the price is worked out</h2>
<ol>
  <li>We take the world price of gold and silver in rupees.</li>
  <li>We add import duty and the usual Indian market premium, so the number is close to what local markets quote.</li>
  <li>22 carat is 22/24 of the 24 carat price. 18 carat is 18/24 of it. Silver is for fine (999) silver.</li>
  <li>GST ({GST}%) and making charges are <strong>not</strong> included.</li>
</ol>
<p>Prices are checked {times_word()} a day, around {E(times_text())} India time.
Every shop sets its own price, so always check with your jeweller before you buy.</p>
<h2>Our guides</h2>
<p>Our guides are written to help ordinary buyers understand purity, hallmarks, making charges, taxes and selling.
Each guide shows the date it was last updated. If you find a mistake, please <a href="contact.html">tell us</a> and we'll fix it.</p>
<h2>Independence</h2>
<p>We are not a jewellery shop and we don't sell gold. We are not paid by any jeweller to show their prices.</p>
""", f"About {SITE}: how we work out daily gold and silver rates.")
    text_page("disclaimer.html", "Disclaimer", "Disclaimer", f"""
<p>The gold and silver prices on {E(SITE)} are a guide only. They are worked out from public world prices and may be
different from the price at any shop, bank or market. They do not include GST, making charges or other fees.</p>
<p>We try to keep the numbers and guides correct, but we cannot promise that they are always right or up to date.
Please check the price with your jeweller before you buy or sell.</p>
<p>Nothing on this site is financial, tax or legal advice. For decisions about your money, speak to a qualified adviser.
We are not responsible for any loss from using the information on this site.</p>
""", f"{SITE} prices and guides are for information only.")
    text_page("privacy.html", "Privacy policy", "Privacy policy", f"""
<p>{E(SITE)} does not ask for your name and does not need an account. The calculators and converters run only inside
your browser; nothing you type in them is sent to us.</p>
<h2>Cookies</h2>
<p>We do not set any cookies ourselves.</p>
<h2>Advertising</h2>
<p>This site may show advertisements served by Google AdSense. Google and its partners use cookies to show ads based on
your earlier visits to this and other websites. You can turn off personalised ads in
<a href="https://adssettings.google.com" rel="noopener">Google Ads Settings</a>, and learn more in
<a href="https://policies.google.com/technologies/ads" rel="noopener">how Google uses cookies in advertising</a>.</p>
<h2>Server logs</h2>
<p>Like every website, our hosting company may keep basic technical logs (such as IP address and browser type)
for security. We do not sell or share any personal information.</p>
<h2>Contact</h2>
<p>Questions about this policy: <a href="mailto:{email}">{email}</a></p>
""", f"{SITE} privacy policy: no accounts, no cookies from us, advertising cookies explained.")
    text_page("terms.html", "Terms of use", "Terms of use", f"""
<p>By using {E(SITE)} you agree to these terms.</p>
<h2>Use of the information</h2>
<p>Prices, charts, calculators and guides are provided for general information. They may contain errors or delays.
Do not rely on them alone for buying, selling or investing.</p>
<h2>Content</h2>
<p>The text, charts and design of this site belong to {E(SITE)}. You may share links to any page. Please don't copy whole
pages or guides to other websites without permission.</p>
<h2>Links to other sites</h2>
<p>Some pages link to other websites, such as Google's ad settings. We are not responsible for their content.</p>
<h2>Changes</h2>
<p>We may update these terms. The latest version is always on this page.</p>
<p>Questions: <a href="mailto:{email}">{email}</a></p>
""", f"Terms of use for {SITE}.")
    text_page("contact.html", "Contact", "Contact us", f"""
<p>Found a wrong price or a mistake in a guide, or want your city added? Send us an email:</p>
<p class="big-link"><a href="mailto:{email}">{email}</a></p>
<p>For prices, please tell us the city, the date and the price you saw.</p>
""", f"Contact {SITE}.")
    write("404.html", page("404.html", "", f"Page not found | {SITE}", "This page does not exist.",
          '<header class="page-head"><h1>Page not found</h1></header>'
          '<p>This page does not exist. <a href="index.html">See today\'s gold rate</a> or <a href="guides.html">browse our guides</a>.</p>'))
    PAGES.remove("404.html")


def seo_files():
    latest = max(gold_hist(c["slug"])[0]["d"] for c in GOLD_CITIES)
    urls = "".join(f"<url><loc>{E(BASE_URL + '/' + ('' if p == 'index.html' else p))}</loc><lastmod>{latest}</lastmod></url>"
                   for p in PAGES)
    write("sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n'
                         f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n")


def main():
    if not GOLD_CITIES:
        raise SystemExit("data/rates.json has no gold prices yet. Run: python tools/update_rates.py demo")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(STATIC, OUT / "assets")
    if (ROOT / "_headers").exists():
        shutil.copy(ROOT / "_headers", OUT / "_headers")
    home_page()
    for city in GOLD_CITIES:
        gold_city_page(city)
    if SILVER_CITIES:
        silver_home()
        for city in SILVER_CITIES:
            silver_city_page(city)
    guide_pages()
    tools_pages()
    legal_pages()
    seo_files()
    print(f"Built {len(PAGES)} pages (+404) into {OUT}" + ("  (SAMPLE prices)" if RATES.get("sample") else ""))


if __name__ == "__main__":
    main()
