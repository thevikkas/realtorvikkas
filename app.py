#!/usr/bin/env python3
"""Realtor Vikkas — a self-contained real-estate web app.

Standard library only. Run:  python3 app.py   then open http://localhost:8000

Public site + customer panel + owner (admin) panel, backed by SQLite.
"""

import gzip
import hashlib
import hmac
import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
from http import cookies as http_cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import auth
from database import get_conn, init_db, now

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(HERE, "static")

# Vendored, dependency-free QR encoder (for per-listing QR codes). Kept in the
# repo so it works on the host with no pip install; degrades gracefully if absent.
import sys as _sys
_sys.path.insert(0, os.path.join(HERE, "vendor"))
try:
    import segno as _segno
except Exception:
    _segno = None

# Cache-busting version for /static/app.css — changes whenever the file changes,
# so browsers pick up a new stylesheet immediately after a deploy while still
# caching it aggressively between deploys.
try:
    _ASSET_V = str(int(os.path.getmtime(os.path.join(STATIC_DIR, "app.css"))))
except OSError:
    _ASSET_V = "1"
PORT = int(os.environ.get("PORT") or 10000)   # Render routes to $PORT (default 10000)
# Secret for the Excel→website sync endpoint. Set a strong value on Render (env
# var SYNC_KEY); the fallback lets it work locally for testing.
SYNC_KEY = os.environ.get("SYNC_KEY") or "vikkas-jaipur-8753"

# Canonical base URL for SEO (canonical links, Open Graph, sitemap). Apex
# redirects to www, so www is the canonical host.
SITE_BASE = (os.environ.get("SITE_BASE") or "https://www.realtorvikkas.com").rstrip("/")
DEFAULT_DESC = ("Realtor Vikkas — buy, sell and rent flats, plots and villas in Jaipur. "
                "Verified property listings across Vaishali Nagar, Mansarovar, Jagatpura, "
                "C-Scheme, Ajmer Road and more, with owner contacts and site visits.")

# Contact for WhatsApp / Call CTAs (override via env in production).
WHATSAPP = os.environ.get("WHATSAPP") or "919001189003"     # E.164 digits, no '+'
PHONE = os.environ.get("PHONE") or "+919001189003"


def _wa_url(text=""):
    """Build a WhatsApp click-to-chat link, optionally pre-filled with a message."""
    base = "https://wa.me/" + WHATSAPP
    return base + ("?text=" + urllib.parse.quote(text) if text else "")

CITIES = ["Jaipur", "Udaipur", "Jodhpur", "Delhi NCR", "Ahmedabad",
          "Gandhinagar", "Shimla", "Manali"]
PTYPES = ["Villa", "Plot", "Flat", "Townhouse", "Commercial"]

# Price bands for the search filter (INR value, label) — used for Min/Max selects.
PRICE_BANDS = [
    (1_000_000, "₹10 L"), (2_500_000, "₹25 L"), (5_000_000, "₹50 L"),
    (7_500_000, "₹75 L"), (10_000_000, "₹1 Cr"), (15_000_000, "₹1.5 Cr"),
    (20_000_000, "₹2 Cr"), (30_000_000, "₹3 Cr"), (50_000_000, "₹5 Cr"),
    (100_000_000, "₹10 Cr"),
]
# Sort options: key -> (SQL order-by, human label). Insertion order = menu order.
SORTS = {
    "new":        ("featured DESC, created_at DESC", "Newest first"),
    "price_low":  ("price ASC, featured DESC",       "Price: low to high"),
    "price_high": ("price DESC, featured DESC",      "Price: high to low"),
    "area":       ("area_sqft DESC, featured DESC",  "Largest area"),
}

# Investment / resort module.
INVEST_CATEGORIES = ["Plot", "Pre-launch", "Resort / Second Home",
                     "Rental Yield", "Commercial", "Farmhouse"]
# Shown on every investment page. Deliberately makes NO promise of returns.
INVEST_DISCLAIMER = (
    "Property investment carries market risk. Any figures, timelines or attributes shown are "
    "indicative and provided by the seller or owner — they are not guaranteed returns and are "
    "subject to independent due diligence. Realtor Vikkas is a real-estate consultancy, not a "
    "financial adviser. Please verify all details before committing.")

# Market insights / guides module.
INSIGHT_CATEGORIES = ["Guide", "Market Note", "Locality", "Investment"]
EMI_DISCLAIMER = (
    "This EMI estimate is indicative only — it is a standard calculation from the numbers you "
    "enter, not a loan offer. Actual rates, eligibility and charges are decided by your lender.")


def _qr_svg(url):
    """Inline SVG QR code for a URL (dark indigo modules on white), or '' if unavailable."""
    if _segno is None:
        return ""
    try:
        return _segno.make(url, error="m").svg_inline(scale=4, border=2,
                                                       dark="#1B2A4A", light="#ffffff")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def e(s):
    """HTML-escape a value for safe interpolation."""
    return html.escape(str(s if s is not None else ""))


def money(n):
    """Format INR the Indian way: crore / lakh, else plain with commas."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "—"
    if n >= 10_000_000:
        return f"₹{n/10_000_000:.2f} Cr".replace(".00", "")
    if n >= 100_000:
        return f"₹{n/100_000:.1f} L".replace(".0", "")
    return "₹" + f"{n:,}"


def opts(values, selected=""):
    out = []
    for v in values:
        sel = " selected" if str(v) == str(selected) else ""
        out.append(f'<option value="{e(v)}"{sel}>{e(v)}</option>')
    return "".join(out)


def _pos_int(s):
    """Parse a positive integer from a query string, else None (filter ignored)."""
    try:
        v = int(s)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def _sync_int(v):
    """For the sync endpoint: int (incl. 0) when a value is present, else None (skip)."""
    if v is None or v == "":
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _price_opts(selected=""):
    out = []
    for val, lbl in PRICE_BANDS:
        sel = " selected" if str(val) == str(selected) else ""
        out.append(f'<option value="{val}"{sel}>{e(lbl)}</option>')
    return "".join(out)


def _photo_list(photos_url):
    """Split a photos field into a list of image URLs (comma / newline / pipe separated)."""
    if not photos_url:
        return []
    raw = str(photos_url).replace("\n", ",").replace("|", ",")
    return [u.strip() for u in raw.split(",") if u.strip().startswith("http")]


class Request:
    def __init__(self, method, path, query, form, cookies, user):
        self.method = method
        self.path = path
        self.query = query      # dict of str -> str (last value wins)
        self.form = form        # dict of str -> str
        self.cookies = cookies
        self.user = user        # sqlite Row or None

    def q(self, key, default=""):
        return self.query.get(key, default)

    def f(self, key, default=""):
        return (self.form.get(key, default) or "").strip()


class Response:
    def __init__(self, body=b"", status=200, content_type="text/html; charset=utf-8",
                 headers=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.body = body
        self.status = status
        self.content_type = content_type
        self.headers = headers or []

    def set_cookie(self, name, value, max_age=None, delete=False):
        c = http_cookies.SimpleCookie()
        c[name] = value
        c[name]["path"] = "/"
        c[name]["httponly"] = True
        c[name]["samesite"] = "Lax"
        if delete:
            c[name]["max-age"] = 0
        elif max_age:
            c[name]["max-age"] = max_age
        self.headers.append(("Set-Cookie", c[name].OutputString()))
        return self


def redirect(location, msg=None, err=None, cookie=None):
    params = {}
    if msg:
        params["msg"] = msg
    if err:
        params["err"] = err
    if params:
        sep = "&" if "?" in location else "?"
        location = location + sep + urllib.parse.urlencode(params)
    resp = Response(b"", status=303, headers=[("Location", location)])
    if cookie:
        resp.headers.append(("Set-Cookie", cookie))
    return resp


# ---------------------------------------------------------------------------
# Layout / templates
# ---------------------------------------------------------------------------

def layout(title, body, req, active="", description=None, canonical=None,
           head_extra="", noindex=False, og_image=None):
    user = req.user
    if user:
        if user["role"] == "owner":
            links = ('<a href="/owner">Dashboard</a>'
                     '<a href="/owner/properties">Properties</a>'
                     '<a href="/owner/leads">Leads</a>'
                     '<a href="/admin/investments">Investments</a>'
                     '<a href="/admin/insights">Insights</a>'
                     '<a href="/properties">Public Site</a>')
        else:
            links = ('<a href="/properties">Browse</a>'
                     '<a href="/invest">Invest</a>'
                     '<a href="/insights">Insights</a>'
                     '<a href="/account">My Account</a>'
                     '<a href="/account/saved">Saved</a>')
        nav = (f'{links}<span class="who">{e(user["name"])} ·</span>'
               f'<a href="/logout">Log out</a>')
    else:
        nav = ('<a href="/properties">Browse</a>'
               '<a href="/invest">Invest</a>'
               '<a href="/insights">Insights</a>'
               '<a href="/login">Log in</a>'
               '<a class="btn btn-brass btn-sm" href="/register">Sign up</a>')

    flash = ""
    if req.q("msg"):
        flash += f'<div class="flash ok">{e(req.q("msg"))}</div>'
    if req.q("err"):
        flash += f'<div class="flash err">{e(req.q("err"))}</div>'

    # Floating "Request a callback" button — shown to visitors & customers.
    callback = "" if (user and user["role"] == "owner") else _callback_widget(req)
    floats = "" if (user and user["role"] == "owner") else _float_actions(req)

    # --- SEO head ---
    full_title = f"{title} — Realtor Vikkas"
    desc = e(description or DEFAULT_DESC)
    canon = e(canonical or (SITE_BASE + (req.path or "/")))
    _private = req.path.startswith(("/owner", "/account", "/admin")) or \
        req.path in ("/login", "/register", "/logout")
    robots = "noindex,nofollow" if (noindex or _private) else "index,follow"
    og_img = f'\n<meta property="og:image" content="{e(og_image)}">' if og_image else ""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(full_title)}</title>
<meta name="description" content="{desc}">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{canon}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Realtor Vikkas">
<meta property="og:title" content="{e(full_title)}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canon}">{og_img}
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="/static/app.css?v={_ASSET_V}">
{head_extra}
</head>
<body>
<header class="topbar">
  <div class="wrap">
    <a href="/" class="brand">
      <span class="brand-mark">Realtor Vikkas</span>
      <span class="brand-sub">Property Register · Est. Jaipur</span>
    </a>
    <nav class="topnav">{nav}</nav>
  </div>
</header>
<main class="wrap page">
{flash}
{body}
</main>
<footer class="app-foot">Realtor Vikkas — Land &amp; homes across Rajasthan, Delhi, Gujarat &amp; the Himalayas.</footer>
{floats}
{callback}
</body>
</html>"""


def _float_actions(req):
    """Floating WhatsApp + Call buttons for visitors (every public page)."""
    wa = _wa_url("Hi, I found realtorvikkas.com and would like help with a property in Jaipur.")
    return f"""
<div class="fab-stack">
  <a class="fab wa" href="{wa}" target="_blank" rel="noopener" aria-label="Chat on WhatsApp">
    <svg viewBox="0 0 24 24" fill="currentColor" width="26" height="26"><path d="M12 2a10 10 0 0 0-8.6 15.05L2 22l5.1-1.33A10 10 0 1 0 12 2zm0 18.2a8.2 8.2 0 0 1-4.2-1.15l-.3-.18-3 .78.8-2.92-.2-.31A8.2 8.2 0 1 1 12 20.2zm4.6-6.15c-.25-.13-1.47-.72-1.7-.8s-.4-.13-.56.13-.64.8-.79.96-.3.2-.55.07a6.7 6.7 0 0 1-2-1.23 7.4 7.4 0 0 1-1.36-1.7c-.14-.24 0-.37.11-.5s.25-.29.37-.43a1.7 1.7 0 0 0 .25-.42.46.46 0 0 0 0-.44c-.06-.13-.56-1.34-.76-1.83s-.4-.42-.56-.42h-.48a.92.92 0 0 0-.67.31 2.8 2.8 0 0 0-.87 2.08 4.86 4.86 0 0 0 1.02 2.58 11.1 11.1 0 0 0 4.25 3.76c.6.26 1.05.42 1.4.53a3.4 3.4 0 0 0 1.55.1 2.53 2.53 0 0 0 1.66-1.17 2.06 2.06 0 0 0 .14-1.17c-.06-.1-.22-.16-.47-.29z"/></svg>
  </a>
  <a class="fab call" href="tel:{PHONE}" aria-label="Call us">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="24" height="24"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6 19.8 19.8 0 0 1-3.1-8.7A2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.4-1.2a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2Z"/></svg>
  </a>
</div>
<style>
  .fab-stack{{position:fixed;right:18px;bottom:80px;z-index:59;display:flex;flex-direction:column;gap:10px}}
  .fab{{width:52px;height:52px;border-radius:50%;display:flex;align-items:center;justify-content:center;box-shadow:0 6px 18px rgba(16,26,48,.3);color:#fff;transition:transform .2s}}
  .fab:hover{{transform:scale(1.09)}}
  .fab.wa{{background:#25D366}}
  .fab.call{{background:#1B2A4A}}
  @media(max-width:600px){{.fab{{width:48px;height:48px}}}}
</style>"""


def _callback_widget(req):
    """A floating 'Request a callback' button + modal, shown on every public page."""
    return f"""
<button class="btn btn-brass callback-fab" type="button" onclick="document.getElementById('cbDlg').showModal()">📞 Request a callback</button>
<dialog id="cbDlg" class="callback-dlg">
  <form method="post" action="/callback">
    <h3 style="margin:0 0 4px">Request a callback</h3>
    <p style="margin:0 0 14px;color:var(--muted);font-size:.9rem">Leave your number — Realtor Vikkas will call you back.</p>
    <input type="hidden" name="back" value="{e(req.path)}">
    <input type="text" name="website" tabindex="-1" autocomplete="off" aria-hidden="true" style="position:absolute!important;left:-9999px!important;top:-9999px!important;height:1px;width:1px;opacity:0">
    <label>Name</label><input name="name" required>
    <label>Phone</label><input name="phone" required placeholder="+91 …">
    <label>Best time to call</label><input name="preferred" placeholder="e.g. after 6 pm">
    <label>Note (optional)</label><textarea name="note" placeholder="Looking for a 3BHK in Jaipur…"></textarea>
    <div class="cb-actions">
      <button type="button" class="btn btn-ghost btn-sm" onclick="document.getElementById('cbDlg').close()">Cancel</button>
      <button type="submit" class="btn btn-brass btn-sm">Request callback</button>
    </div>
  </form>
</dialog>
<style>
  .callback-fab{{position:fixed;right:18px;bottom:18px;z-index:60;box-shadow:0 6px 20px rgba(0,0,0,.28)}}
  .callback-dlg{{border:none;border-radius:14px;padding:0;max-width:380px;width:92%}}
  .callback-dlg::backdrop{{background:rgba(20,15,8,.45)}}
  .callback-dlg form{{padding:22px}}
  .callback-dlg label{{display:block;margin:10px 0 4px;font-size:.85rem;font-weight:600}}
  .cb-actions{{display:flex;justify-content:flex-end;gap:8px;margin-top:16px}}
</style>"""


def prop_card(p, fav_ids=None):
    fav = ""
    if fav_ids is not None:
        marked = p["id"] in fav_ids
        fav = (f'<form method="post" action="/favorite/{p["id"]}" style="display:inline">'
               f'<button class="fav-btn" title="Toggle saved">{"★" if marked else "☆"}</button></form>')
    specs = []
    if p["bedrooms"]:
        specs.append(f'{p["bedrooms"]} BHK')
    if p["area_sqft"]:
        specs.append(f'{p["area_sqft"]} sqft')
    spec_txt = " · ".join(specs) if specs else p["ptype"]
    alt = f'{e(p["ptype"])} in {e(p["locality"] or p["city"])}, {e(p["city"])}'
    wa = _wa_url(f'Hi, I am interested in {p["title"]} ({p["locality"] or p["city"]}, {p["city"]}) — {SITE_BASE}/property/{p["id"]}. Please share details.')
    if p["photos_url"]:
        media = (f'<img src="{e(p["photos_url"])}" alt="{alt}" loading="lazy" '
                 f'style="width:100%;height:100%;object-fit:cover">')
    else:
        media = ('<svg width="52" height="40" viewBox="0 0 52 40" fill="none" stroke="currentColor" '
                 'stroke-width="1.6" aria-hidden="true" focusable="false"><path d="M6 24 18 10l12 14"/>'
                 '<rect x="10" y="24" width="16" height="12"/><path d="M30 36V18l8-6 8 6v18"/></svg>')
    return f"""<article class="prop-card">
  <div class="prop-vignette">
    <span class="listing-badge">For {e(p["listing"])}</span>
    {_compare_toggle_btn(p["id"])}
    {media}
  </div>
  <div class="prop-body">
    <span class="prop-tag">{e(p["ptype"])} · {e(p["status"])}</span>
    <h3><a href="/property/{p["id"]}">{e(p["title"])}</a></h3>
    <div class="prop-loc">{e(p["locality"])}{", " if p["locality"] else ""}{e(p["city"])}</div>
    <div class="prop-specs">
      <span class="tabular">{e(spec_txt)}</span>
      <span class="price">{money(p["price"])}{"/mo" if p["listing"] == "rent" else ""} {fav}</span>
    </div>
    <div class="prop-actions">
      <a class="pa-btn view" href="/property/{p["id"]}">View</a>
      <a class="pa-btn wa" href="{wa}" target="_blank" rel="noopener">WhatsApp</a>
      <a class="pa-btn call" href="tel:{PHONE}">Call</a>
    </div>
  </div>
</article>"""


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

def _home_ledger_card(p):
    """Render a live property in the homepage 'ledger card' style."""
    specs = []
    if p["bedrooms"]:
        specs.append(f'{p["bedrooms"]} BHK')
    if p["area_sqft"]:
        specs.append(f'{p["area_sqft"]} sq.ft')
    spec_txt = " · ".join(specs) if specs else p["ptype"]
    if p["photos_url"]:
        media = (f'<img src="{e(p["photos_url"])}" alt="{e(p["ptype"])} in {e(p["locality"] or p["city"])}, '
                 f'{e(p["city"])}" loading="lazy" style="width:100%;height:100%;object-fit:cover">')
    else:
        media = ('<svg width="52" height="40" viewBox="0 0 52 40" fill="none" stroke="currentColor" '
                 'stroke-width="1.6" aria-hidden="true"><path d="M6 24 18 10l12 14"/>'
                 '<rect x="10" y="24" width="16" height="12"/><path d="M30 36V18l8-6 8 6v18"/></svg>')
    return f"""<article class="ledger-card reveal">
          <div class="ledger-vignette">{media}</div>
          <div class="ledger-body">
            <span class="ledger-tag">{e(p["ptype"])}</span>
            <h3><a href="/property/{p["id"]}">{e(p["title"])}</a></h3>
            <p class="ledger-loc">{e(p["locality"])}{", " if p["locality"] else ""}{e(p["city"])} — Rajasthan</p>
            <div class="ledger-specs">
              <span class="price">{money(p["price"])}{"/mo" if p["listing"] == "rent" else ""}</span>
              <span>{e(spec_txt)}</span>
            </div>
          </div>
        </article>"""


def home(req):
    """Serve the marketing landing page with LIVE featured Jaipur listings injected."""
    with open(os.path.join(HERE, "index.html"), "r", encoding="utf-8") as fh:
        html = fh.read()
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM properties WHERE status != 'hidden' AND city = 'Jaipur' "
        "ORDER BY featured DESC, created_at DESC LIMIT 6").fetchall()
    conn.close()
    cards = "".join(_home_ledger_card(p) for p in rows) or \
        '<p class="lead" style="grid-column:1/-1">Fresh Jaipur listings are on the way.</p>'
    html = html.replace("<!--LIVE_LISTINGS-->", cards)
    html = html.replace("<!--FLOAT_ACTIONS-->", _float_actions(req))
    return Response(html)


def list_properties(req):
    city = req.q("city")
    ptype = req.q("type")
    listing = req.q("listing")
    kw = req.q("q")
    minp = _pos_int(req.q("minp"))
    maxp = _pos_int(req.q("maxp"))
    beds = _pos_int(req.q("beds"))
    sort = req.q("sort") if req.q("sort") in SORTS else "new"

    conn = get_conn()
    sql = "SELECT * FROM properties WHERE status != 'hidden'"
    args = []
    if city:
        sql += " AND city = ?"; args.append(city)
    if ptype:
        sql += " AND ptype = ?"; args.append(ptype)
    if listing:
        sql += " AND listing = ?"; args.append(listing)
    if minp:
        sql += " AND price >= ?"; args.append(minp)
    if maxp:
        sql += " AND price <= ?"; args.append(maxp)
    if beds:
        sql += " AND bedrooms >= ?"; args.append(beds)
    if kw:
        sql += " AND (title LIKE ? OR locality LIKE ? OR description LIKE ?)"
        args += [f"%{kw}%"] * 3
    sql += " ORDER BY " + SORTS[sort][0]
    rows = conn.execute(sql, args).fetchall()

    fav_ids = set()
    if req.user:
        fav_ids = {r["property_id"] for r in conn.execute(
            "SELECT property_id FROM favorites WHERE user_id = ?", (req.user["id"],)).fetchall()}
    conn.close()

    cards = "".join(prop_card(p, fav_ids if req.user else None) for p in rows) or \
        '<div class="empty">No listings match those filters yet. Try widening your price or type — or <a href="/properties">reset the filters</a>.</div>'

    filtered = any([city, ptype, listing, kw, minp, maxp, beds])
    count_line = (f'{len(rows)} propert{"y" if len(rows) == 1 else "ies"} '
                  + ("match your filters" if filtered else "in Jaipur — Vaishali Nagar, "
                     "Mansarovar, Jagatpura, C-Scheme, Ajmer Road and more."))
    bed_opts = '<option value="">Any BHK</option>' + "".join(
        f'<option value="{n}"{" selected" if beds == n else ""}>{n}+ BHK</option>' for n in (1, 2, 3, 4, 5))
    sort_opts = "".join(
        f'<option value="{k}"{" selected" if sort == k else ""}>{e(lbl)}</option>'
        for k, (_o, lbl) in SORTS.items())

    body = f"""
<p class="eyebrow">The Register · Jaipur</p>
<h1>Property in Jaipur — flats, plots &amp; villas</h1>
<p class="lead">{count_line} <span class="tool-hint">· Tap <b>⇄ Compare</b> on any two, or use the <a href="/emi">EMI calculator</a>.</span></p>

<form class="filters" method="get" action="/properties">
  <div class="field"><label>City</label><select name="city"><option value="">All cities</option>{opts(CITIES, city)}</select></div>
  <div class="field"><label>Type</label><select name="type"><option value="">All types</option>{opts(PTYPES, ptype)}</select></div>
  <div class="field"><label>Listing</label><select name="listing"><option value="">Buy &amp; Rent</option><option value="buy"{" selected" if listing=="buy" else ""}>Buy</option><option value="rent"{" selected" if listing=="rent" else ""}>Rent</option></select></div>
  <div class="field"><label>Min price</label><select name="minp"><option value="">No min</option>{_price_opts(minp)}</select></div>
  <div class="field"><label>Max price</label><select name="maxp"><option value="">No max</option>{_price_opts(maxp)}</select></div>
  <div class="field"><label>Bedrooms</label><select name="beds">{bed_opts}</select></div>
  <div class="field"><label>Sort by</label><select name="sort">{sort_opts}</select></div>
  <div class="field"><label>Keyword</label><input name="q" value="{e(kw)}" placeholder="locality, project…"></div>
  <div class="filter-actions"><button class="btn btn-brass" type="submit">Filter</button><a class="btn btn-ghost" href="/properties">Reset</a></div>
</form>

<div class="prop-grid">{cards}</div>
{_COMPARE_ASSETS}
"""
    seo_title = "Properties in Jaipur — Flats, Plots & Villas for Sale & Rent"
    seo_desc = ("Browse verified property listings in Jaipur — flats, plots and villas for "
                "sale and rent in Vaishali Nagar, Mansarovar, Jagatpura, C-Scheme, Ajmer Road "
                "and more. Owner contacts and easy site visits with Realtor Vikkas.")
    return Response(layout(seo_title, body, req, description=seo_desc,
                           canonical=SITE_BASE + "/properties"))


def _gallery(photos, alt):
    """Main image + clickable thumbnails (inline JS swaps the main image; no libraries)."""
    main = photos[0]
    if len(photos) == 1:
        return (f'<div class="gallery"><img id="galMain" class="gallery-main" '
                f'src="{e(main)}" alt="{alt}" loading="lazy"></div>')
    thumbs = "".join(
        f'<button type="button" class="thumb{" active" if i == 0 else ""}" '
        f"onclick=\"galSet(this,'{e(u)}')\"><img src=\"{e(u)}\" alt=\"\" loading=\"lazy\"></button>"
        for i, u in enumerate(photos))
    js = ("<script>function galSet(b,src){var m=document.getElementById('galMain');"
          "if(m){m.src=src;}var t=b.parentNode.querySelectorAll('.thumb');"
          "for(var i=0;i<t.length;i++){t[i].classList.remove('active');}"
          "b.classList.add('active');}</script>")
    return (f'<div class="gallery"><img id="galMain" class="gallery-main" src="{e(main)}" '
            f'alt="{alt}" loading="lazy"><div class="gallery-thumbs">{thumbs}</div></div>{js}')


def _amenities_block(p):
    raw = p["amenities"] if "amenities" in p.keys() else ""
    items = [a.strip() for a in str(raw or "").replace("\n", ",").split(",") if a.strip()]
    if not items:
        return ""
    chips = "".join(f'<li class="amenity">{e(a)}</li>' for a in items)
    return (f'<section class="detail-section"><h2>Amenities</h2>'
            f'<ul class="amenities">{chips}</ul></section>')


def _location_block(p):
    loc = p["locality"] or p["city"]
    query = urllib.parse.quote_plus(f'{loc}, {p["city"]}, Rajasthan, India')
    embed = f"https://maps.google.com/maps?q={query}&z=13&output=embed"
    link = f"https://www.google.com/maps/search/?api=1&query={query}"
    # Facade: don't load the third-party map until the visitor asks — faster first paint,
    # no cross-site request on page load, and it still works with JS.
    return (f'<section class="detail-section"><h2>Location</h2>'
            f'<p class="lead">{e(loc)}, {e(p["city"])} — Rajasthan</p>'
            f'<div class="map-embed map-facade" role="button" tabindex="0" data-embed="{embed}" '
            f'onclick="loadMap(this)" onkeydown="if(event.key===\'Enter\')loadMap(this)" '
            f'aria-label="Load map of {e(loc)}, {e(p["city"])}">'
            f'<div class="map-facade-inner"><span class="map-pin" aria-hidden="true">📍</span>'
            f'<span>Tap to load the map</span></div></div>'
            f'<p style="margin-top:.7rem"><a class="btn btn-ghost btn-sm" href="{link}" '
            f'target="_blank" rel="noopener">📍 Open in Google Maps</a></p>'
            f'<script>function loadMap(el){{var s=el.getAttribute("data-embed");if(!s)return;'
            f'el.innerHTML=\'<iframe title="Map" src="\'+s+\'" loading="lazy" '
            f'referrerpolicy="no-referrer-when-downgrade"></iframe>\';'
            f'el.classList.remove("map-facade");el.removeAttribute("onclick");}}</script></section>')


def _similar(conn, p, limit=3):
    """Up to `limit` other live listings — same city+type first, then same city."""
    seen = {p["id"]}
    out = []
    for sql, args in (
        ("SELECT * FROM properties WHERE status!='hidden' AND city=? AND ptype=? AND id!=? "
         "ORDER BY featured DESC, created_at DESC LIMIT 6", (p["city"], p["ptype"], p["id"])),
        ("SELECT * FROM properties WHERE status!='hidden' AND city=? AND id!=? "
         "ORDER BY featured DESC, created_at DESC LIMIT 6", (p["city"], p["id"])),
    ):
        for r in conn.execute(sql, args).fetchall():
            if r["id"] not in seen:
                out.append(r)
                seen.add(r["id"])
                if len(out) >= limit:
                    return out
    return out


def property_detail(req, pid):
    conn = get_conn()
    p = conn.execute("SELECT * FROM properties WHERE id = ?", (pid,)).fetchone()
    if not p or p["status"] == "hidden":
        conn.close()
        return not_found(req)
    owner = conn.execute("SELECT name, phone, email FROM users WHERE id = ?", (p["owner_id"],)).fetchone()
    similar = _similar(conn, p)
    conn.close()

    prefill_name = e(req.user["name"]) if req.user else ""
    prefill_email = e(req.user["email"]) if req.user else ""
    prefill_phone = e(req.user["phone"]) if req.user else ""

    d_alt = f'{e(p["ptype"])} in {e(p["locality"] or p["city"])}, {e(p["city"])}'
    _loc = f'{p["locality"] or p["city"]}, {p["city"]}'
    _url = f'{SITE_BASE}/property/{p["id"]}'
    wa_detail = _wa_url(f'Hi, I am interested in {p["title"]} ({_loc}) — {_url}. Please share more details.')
    wa_visit = _wa_url(f'Hi, I would like to schedule a site visit for {p["title"]} ({_loc}) — {_url}.')
    photos = _photo_list(p["photos_url"])
    if photos:
        banner_block = _gallery(photos, d_alt)
    else:
        banner_block = ('<div class="detail-banner"><svg width="90" height="70" viewBox="0 0 52 40" '
                        'fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true" '
                        'focusable="false"><path d="M6 24 18 10l12 14"/><rect x="10" y="24" width="16" '
                        'height="12"/><path d="M30 36V18l8-6 8 6v18"/></svg></div>')

    # price per sqft — a genuine calculation from real data (buy listings only)
    persqft = ""
    if p["listing"] == "buy" and p["price"] and p["area_sqft"]:
        persqft = f'<div><div class="k">Price / sqft</div><div class="v">₹{int(p["price"]/p["area_sqft"]):,}</div></div>'

    amen_html = _amenities_block(p)
    loc_html = _location_block(p)
    sim_html = ""
    if similar:
        sim_html = ('<section class="detail-section"><h2>Similar in ' + e(p["city"]) + '</h2>'
                    '<div class="prop-grid">' + "".join(prop_card(s) for s in similar) + "</div></section>")

    # QR (scan to open/share) + EMI shortcut in the aside
    qr_svg = _qr_svg(f"{SITE_BASE}/property/{p['id']}")
    qr_card = (f'<div class="card qr-card"><h3 style="font-size:1.05rem;margin-bottom:.3rem">Scan &amp; share</h3>'
               f'<p class="lead" style="font-size:.8rem;margin-bottom:.6rem">Point a phone camera here to open this listing.</p>'
               f'<div class="qr-box">{qr_svg}</div></div>') if qr_svg else ""
    emi_href = f"/emi?amount={p['price']}" if p["listing"] == "buy" and p["price"] else "/emi"
    emi_card = (f'<div class="card"><h3 style="font-size:1.05rem;margin-bottom:.3rem">Plan your budget</h3>'
                f'<p class="lead" style="font-size:.8rem;margin-bottom:.7rem">'
                + ("See the monthly EMI for this price." if p["listing"] == "buy" else "Work out a home-loan EMI.")
                + f'</p><a class="btn btn-ghost btn-sm" href="{emi_href}">🧮 EMI calculator</a></div>')

    body = f"""
<p><a class="muted-link" href="/properties">← Back to listings</a></p>
<div class="detail-head">
  <div>
    {banner_block}
    <p class="eyebrow" style="margin-top:1.2rem">{e(p["ptype"])} · For {e(p["listing"])}</p>
    <h1>{e(p["title"])}</h1>
    <p class="lead">{e(p["locality"])}{", " if p["locality"] else ""}{e(p["city"])}</p>
    <div class="spec-list">
      <div><div class="k">Price</div><div class="v price">{money(p["price"])}{"/mo" if p["listing"]=="rent" else ""}</div></div>
      {persqft}
      <div><div class="k">Type</div><div class="v">{e(p["ptype"])}</div></div>
      <div><div class="k">Status</div><div class="v"><span class="pill {e(p["status"])}">{e(p["status"])}</span></div></div>
      <div><div class="k">Area</div><div class="v">{e(p["area_sqft"] or "—")} sqft</div></div>
      <div><div class="k">Bedrooms</div><div class="v">{e(p["bedrooms"] or "—")}</div></div>
      <div><div class="k">Bathrooms</div><div class="v">{e(p["bathrooms"] or "—")}</div></div>
      <div><div class="k">Locality</div><div class="v">{e(p["locality"] or p["city"])}</div></div>
      <div><div class="k">Listed by</div><div class="v">{e(owner["name"] if owner else "Realtor Vikkas")}</div></div>
    </div>
    <div class="detail-actions">
      <a class="da-btn wa" href="{wa_detail}" target="_blank" rel="noopener">💬 WhatsApp</a>
      <a class="da-btn call" href="tel:{PHONE}">📞 Call Now</a>
      <a class="da-btn visit" href="{wa_visit}" target="_blank" rel="noopener">📅 Schedule Site Visit</a>
    </div>
    <p>{e(p["description"])}</p>
  </div>

  <aside>
    <div class="card">
      <h3 style="font-size:1.2rem;margin-bottom:0.3rem">Enquire about this property</h3>
      <p class="lead" style="font-size:0.85rem;margin-bottom:1rem">Send Realtor Vikkas a message and the team will be in touch.</p>
      <form method="post" action="/enquiry">
        <input type="hidden" name="property_id" value="{p["id"]}">
        <input type="text" name="website" tabindex="-1" autocomplete="off" aria-hidden="true" style="position:absolute!important;left:-9999px!important;top:-9999px!important;height:1px;width:1px;opacity:0">
        <div style="margin-bottom:0.8rem"><label>Name</label><input name="name" required value="{prefill_name}"></div>
        <div style="margin-bottom:0.8rem"><label>Email</label><input name="email" type="email" required value="{prefill_email}"></div>
        <div style="margin-bottom:0.8rem"><label>Phone</label><input name="phone" value="{prefill_phone}"></div>
        <div style="margin-bottom:0.8rem"><label>Message</label><textarea name="message" placeholder="I'd like to arrange a visit…"></textarea></div>
        <button class="btn btn-brass" type="submit" style="width:100%">Send enquiry</button>
      </form>
    </div>
    {emi_card}
    {qr_card}
  </aside>
</div>
{amen_html}
{loc_html}
{sim_html}
"""
    # --- dynamic SEO title + description ---
    bhk = f"{p['bedrooms']}BHK " if p["bedrooms"] else ""
    loc = p["locality"] or p["city"]
    seo_title = f"{bhk}{p['ptype']} in {loc}, {p['city']} — {money(p['price'])}"
    bits = []
    if p["bedrooms"]:
        bits.append(f"{p['bedrooms']} BHK")
    if p["area_sqft"]:
        bits.append(f"{p['area_sqft']} sqft")
    spec = ", ".join(bits)
    rent = "/month" if p["listing"] == "rent" else ""
    seo_desc = (f"{p['ptype']} for {p['listing']} in {loc}, {p['city']} at {money(p['price'])}{rent}."
                + (f" {spec}." if spec else "")
                + (f" {p['description'][:140].strip()}" if p["description"] else "")).strip()

    # --- Schema.org RealEstateListing (JSON-LD) ---
    ld = {
        "@context": "https://schema.org",
        "@type": "RealEstateListing",
        "name": seo_title,
        "url": SITE_BASE + f"/property/{p['id']}",
        "datePosted": p["created_at"],
        "description": p["description"] or seo_desc,
        "address": {
            "@type": "PostalAddress",
            "streetAddress": p["locality"] or "",
            "addressLocality": p["city"],
            "addressRegion": "Rajasthan",
            "addressCountry": "IN",
        },
        "offers": {
            "@type": "Offer",
            "price": p["price"],
            "priceCurrency": "INR",
            "availability": ("https://schema.org/InStock" if p["status"] == "available"
                             else "https://schema.org/SoldOut"),
        },
    }
    if p["bedrooms"]:
        ld["numberOfBedrooms"] = p["bedrooms"]
    if p["area_sqft"]:
        ld["floorSize"] = {"@type": "QuantitativeValue", "value": p["area_sqft"], "unitCode": "FTK"}
    jsonld = ('<script type="application/ld+json">'
              + json.dumps(ld).replace("</", "<\\/") + "</script>")

    return Response(layout(seo_title, body, req, description=seo_desc,
                           canonical=SITE_BASE + f"/property/{p['id']}", head_extra=jsonld))


def submit_enquiry(req):
    pid = req.f("property_id")
    if _is_spam(req.f("name"), req.f("message"), req.f("website")):
        return redirect(f"/property/{pid}", msg="Thank you — your enquiry has been sent to Realtor Vikkas.")
    conn = get_conn()
    p = conn.execute("SELECT id FROM properties WHERE id = ?", (pid,)).fetchone()
    if not p:
        conn.close()
        return redirect("/properties", err="That property no longer exists.")
    conn.execute(
        "INSERT INTO enquiries (property_id, customer_id, name, email, phone, message, status, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (pid, req.user["id"] if req.user else None, req.f("name"), req.f("email"),
         req.f("phone"), req.f("message"), "new", now()))
    prop = conn.execute("SELECT title FROM properties WHERE id = ?", (pid,)).fetchone()
    conn.commit()
    conn.close()
    _save_lead(req.f("name"), req.f("phone"), prop["title"] if prop else "", req.f("message"))
    return redirect(f"/property/{pid}", msg="Thank you — your enquiry has been sent to Realtor Vikkas.")


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

def auth_aside(role):
    """Left-hand brand panel for the split auth pages."""
    if role == "owner":
        head = "Manage your listings and leads in one place."
        points = [
            "List, edit and feature properties across every region.",
            "Track buyer enquiries from a single leads inbox.",
            "See what's converting with a live dashboard.",
        ]
    else:
        head = "Find your next home, land or investment with confidence."
        points = [
            "Browse verified listings across Rajasthan, Delhi NCR &amp; Gujarat.",
            "Save your favourites and revisit them anytime.",
            "Enquire directly and hear back from the owner.",
        ]
    check = ('<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
             'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>')
    lis = "".join(f"<li>{check}<span>{p}</span></li>" for p in points)
    return f"""
  <aside class="auth-aside">
    <div>
      <div class="auth-logo">Realtor Vikkas</div>
      <div class="auth-logo-sub">Property Register · Est. Jaipur</div>
    </div>
    <div>
      <h2>{head}</h2>
      <ul class="auth-points">{lis}</ul>
    </div>
    <div class="auth-aside-foot">Trusted by buyers &amp; owners across Rajasthan, Delhi NCR, Gujarat &amp; the Himalayas.</div>
  </aside>"""


ICON_MAIL = ('<svg class="i-lead" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
             'stroke-width="1.7"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg>')
ICON_LOCK = ('<svg class="i-lead" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
             'stroke-width="1.7"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>')
ICON_USER = ('<svg class="i-lead" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
             'stroke-width="1.7"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>')
ICON_PHONE = ('<svg class="i-lead" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
              'stroke-width="1.7"><path d="M4 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L20 13l2 5v0a2 2 0 0 1-2 2 16 16 0 0 1-16-16 2 2 0 0 1 2-2Z"/></svg>')
ICON_MAIL_DARK = ('<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                  'stroke-width="1.8"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg>')

PW_TOGGLE_JS = """
<script>
document.querySelectorAll('.pw-toggle').forEach(function(b){
  b.addEventListener('click', function(){
    var i = this.closest('.input-wrap').querySelector('input');
    var show = i.type === 'password';
    i.type = show ? 'text' : 'password';
    this.textContent = show ? 'Hide' : 'Show';
  });
});
</script>"""


COUNTRY_CODES = ["+91", "+1", "+44", "+971", "+61", "+65"]


def login_form(req):
    """Customer login is phone-first (image style). Email + owner use the split form."""
    if req.q("as") == "owner":
        return login_form_email(req, "owner")
    if req.q("method") == "email":
        return login_form_email(req, "customer")
    return login_form_phone(req)


def login_form_phone(req):
    ccode_opts = "".join(
        f'<option value="{c}"{" selected" if c == "+91" else ""}>{c}</option>' for c in COUNTRY_CODES)
    body = f"""
<div class="login-modal">
  <div class="login-modal-head">
    <h1>Login / Register</h1>
    <a class="close" href="/" title="Close" aria-label="Close">&times;</a>
  </div>
  <p class="prompt">Enter your phone number and password to continue.</p>
  <form method="post" action="/login" autocomplete="on">
    <div class="boxed-field">
      <div class="bf-label">Phone Number</div>
      <div class="bf-row">
        <select class="ccode" name="ccode" aria-label="Country code">{ccode_opts}</select>
        <input name="phone" type="tel" inputmode="numeric" placeholder="98765 43210" autocomplete="tel-national" required autofocus>
      </div>
    </div>
    <div class="boxed-field">
      <div class="bf-label">Password</div>
      <div class="bf-row">
        <input class="has-toggle" name="password" type="password" placeholder="Your password" autocomplete="current-password" required>
        <button type="button" class="pw-toggle">Show</button>
      </div>
    </div>
    <button class="btn-continue" type="submit">Continue</button>
  </form>
  <a class="btn-outline" href="/login?method=email">{ICON_MAIL_DARK} Login with Email</a>
  <p class="login-owner-link">Property owner? <a class="muted-link" href="/login?as=owner">Owner login</a></p>
  <p class="login-terms">By clicking you agree to our <a href="/terms">Terms and Conditions</a>.</p>
</div>
{PW_TOGGLE_JS}
"""
    return Response(layout("Login", body, req))


def login_form_email(req, role):
    cust_active = " is-active" if role == "customer" else ""
    own_active = " is-active" if role == "owner" else ""
    if role == "owner":
        sub = "Sign in to your owner dashboard to manage listings and leads."
        phone_switch = ""
    else:
        sub = "Sign in to browse, save and enquire on properties."
        phone_switch = ('<p class="login-owner-link">Prefer your phone? '
                        '<a class="muted-link" href="/login">Login with phone number</a></p>')
    body = f"""
<div class="auth-shell">
  {auth_aside(role)}
  <div class="auth-main">
    <div class="auth-tabs">
      <a class="auth-tab{cust_active}" href="/login?method=email">Login</a>
      <a class="auth-tab{own_active}" href="/login?as=owner">Owner login</a>
    </div>
    <h1>Welcome back</h1>
    <p class="auth-sub">{sub}</p>
    <form method="post" action="/login" autocomplete="on">
      <input type="hidden" name="ctx" value="{role}">
      <div class="field-group">
        <label>Email address</label>
        <div class="input-wrap">{ICON_MAIL}<input name="email" type="email" placeholder="you@example.com" autocomplete="email" required autofocus></div>
      </div>
      <div class="field-group">
        <label>Password</label>
        <div class="input-wrap">{ICON_LOCK}<input class="has-toggle" name="password" type="password" placeholder="Your password" autocomplete="current-password" required>
          <button type="button" class="pw-toggle">Show</button></div>
      </div>
      <div class="auth-row">
        <label class="check"><input type="checkbox" name="remember" checked> Keep me signed in</label>
        <a class="muted-link" href="mailto:owner@realtorvikkas.in?subject=Password%20reset">Forgot password?</a>
      </div>
      <button class="btn btn-brass" type="submit">Log in</button>
    </form>
    <p class="auth-alt">New to Realtor Vikkas? <a class="muted-link" href="/register">Create an account</a></p>
    {phone_switch}
  </div>
</div>
{PW_TOGGLE_JS}
"""
    return Response(layout("Log in", body, req))


def phone_digits(value):
    """Last 10 digits of a phone number, ignoring country code, spaces and symbols."""
    return re.sub(r"\D", "", value or "")[-10:]


def login(req):
    email = req.f("email").strip().lower()
    phone = req.f("phone").strip()
    by_phone = bool(phone) and not email
    conn = get_conn()
    if by_phone:
        digits = phone_digits(phone)
        u = None
        if len(digits) == 10:
            for row in conn.execute("SELECT * FROM users").fetchall():
                if phone_digits(row["phone"]) == digits:
                    u = row
                    break
    else:
        u = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    if not u or not auth.verify_password(req.f("password"), u["password_hash"]):
        if by_phone:
            return redirect("/login", err="Invalid phone number or password.")
        target = "/login?as=owner" if req.f("ctx") == "owner" else "/login?method=email"
        return redirect(target, err="Invalid email or password.")
    token = auth.create_session(u["id"])
    resp = redirect("/owner" if u["role"] == "owner" else "/account",
                    msg=f"Welcome back, {u['name']}.")
    # "Keep me signed in" → 14-day persistent cookie; otherwise a session cookie.
    max_age = 14 * 24 * 3600 if req.f("remember") else None
    resp.set_cookie("session", token, max_age=max_age)
    return resp


def register_form(req):
    body = f"""
<div class="auth-shell">
  {auth_aside("customer")}
  <div class="auth-main">
    <h1>Create your account</h1>
    <p class="auth-sub">Join the register to save listings and enquire in seconds — it's free.</p>
    <form method="post" action="/register" autocomplete="on">
      <div class="field-group">
        <label>Full name</label>
        <div class="input-wrap">{ICON_USER}<input name="name" placeholder="Your name" autocomplete="name" required autofocus></div>
      </div>
      <div class="field-group">
        <label>Email address</label>
        <div class="input-wrap">{ICON_MAIL}<input name="email" type="email" placeholder="you@example.com" autocomplete="email" required></div>
      </div>
      <div class="field-group">
        <label>Phone number <span style="font-weight:400;text-transform:none;letter-spacing:0">(you can log in with this)</span></label>
        <div class="input-wrap">{ICON_PHONE}<input name="phone" type="tel" inputmode="numeric" placeholder="+91 98765 43210" autocomplete="tel" required></div>
      </div>
      <div class="field-group">
        <label>Password</label>
        <div class="input-wrap">{ICON_LOCK}<input class="has-toggle" name="password" type="password" placeholder="At least 6 characters" minlength="6" autocomplete="new-password" required>
          <button type="button" class="pw-toggle">Show</button></div>
      </div>
      <button class="btn btn-brass" type="submit">Create account</button>
    </form>
    <p class="auth-alt">Already registered? <a class="muted-link" href="/login">Log in</a></p>
    <div class="demo-hint">Are you a property owner? <a class="muted-link" href="/login?as=owner">Use the owner login</a> to reach your dashboard.</div>
  </div>
</div>
{PW_TOGGLE_JS}
"""
    return Response(layout("Sign up", body, req))


def register(req):
    name, email, pw = req.f("name"), req.f("email").lower(), req.f("password")
    phone = req.f("phone").strip()
    if len(pw) < 6 or not name or not email or not phone:
        return redirect("/register", err="Please fill every field (password 6+ chars).")
    if len(phone_digits(phone)) != 10:
        return redirect("/register", err="Please enter a valid 10-digit phone number.")
    conn = get_conn()
    if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
        conn.close()
        return redirect("/register", err="An account with that email already exists.")
    digits = phone_digits(phone)
    if any(phone_digits(r["phone"]) == digits for r in conn.execute("SELECT phone FROM users").fetchall()):
        conn.close()
        return redirect("/register", err="An account with that phone number already exists.")
    uid = conn.execute(
        "INSERT INTO users (name, email, phone, password_hash, role, created_at) VALUES (?,?,?,?,?,?)",
        (name, email, phone, auth.hash_password(pw), "customer", now())).lastrowid
    conn.commit()
    conn.close()
    token = auth.create_session(uid)
    resp = redirect("/account", msg=f"Welcome, {name}! Your account is ready.")
    resp.set_cookie("session", token, max_age=14 * 24 * 3600)
    return resp


def logout(req):
    token = req.cookies.get("session")
    auth.destroy_session(token)
    resp = redirect("/", msg="You have been logged out.")
    resp.set_cookie("session", "", delete=True)
    return resp


def terms_page(req):
    body = """
<div class="card" style="max-width:760px;margin:1.5rem auto">
  <p class="eyebrow">Legal</p>
  <h1 style="font-size:1.7rem">Terms &amp; Conditions</h1>
  <p class="lead" style="margin-top:0.6rem">A plain-language summary of how Realtor Vikkas works.</p>
  <div style="margin-top:1.4rem;display:flex;flex-direction:column;gap:1rem;color:var(--muted);font-size:0.92rem;line-height:1.65">
    <p><b style="color:var(--ink)">1. Accounts.</b> You are responsible for keeping your login details private. Provide accurate contact information so owners can reach you about enquiries.</p>
    <p><b style="color:var(--ink)">2. Listings.</b> Property details are provided by owners and are indicative only. Verify all details, pricing and documents independently before any transaction.</p>
    <p><b style="color:var(--ink)">3. Enquiries.</b> Submitting an enquiry shares your name and contact details with the property owner so they can respond.</p>
    <p><b style="color:var(--ink)">4. Acceptable use.</b> Do not post unlawful, misleading or infringing content, and do not misuse the platform or other users' data.</p>
    <p><b style="color:var(--ink)">5. Liability.</b> Realtor Vikkas is a listing platform and is not a party to any deal between buyers, renters and owners.</p>
    <p style="font-size:0.82rem">Questions? Email <a class="muted-link" href="mailto:owner@realtorvikkas.in">owner@realtorvikkas.in</a>.</p>
  </div>
  <p style="margin-top:1.4rem"><a class="btn btn-ghost" href="/login">← Back to login</a></p>
</div>
"""
    return Response(layout("Terms & Conditions", body, req))


# ---------------------------------------------------------------------------
# Customer panel
# ---------------------------------------------------------------------------

def account(req):
    conn = get_conn()
    enq = conn.execute(
        "SELECT en.*, p.title, p.city FROM enquiries en "
        "LEFT JOIN properties p ON p.id = en.property_id "
        "WHERE en.customer_id = ? ORDER BY en.created_at DESC", (req.user["id"],)).fetchall()
    fav_count = conn.execute("SELECT COUNT(*) c FROM favorites WHERE user_id = ?",
                             (req.user["id"],)).fetchone()["c"]
    conn.close()

    rows = "".join(
        f"<tr><td>{e(en['title'] or 'Property removed')}</td><td>{e(en['city'] or '')}</td>"
        f"<td>{e(en['message'])[:70]}</td><td><span class='pill {e(en['status'])}'>{e(en['status'])}</span></td>"
        f"<td class='tabular'>{e(en['created_at'][:10])}</td></tr>"
        for en in enq) or "<tr><td colspan='5' class='empty'>You haven't sent any enquiries yet.</td></tr>"

    body = f"""
<p class="eyebrow">Customer panel</p>
<h1>Welcome, {e(req.user['name'])}</h1>
<div class="stat-row" style="margin-top:1.5rem">
  <div class="stat"><div class="n">{len(enq)}</div><div class="l">Enquiries sent</div></div>
  <div class="stat"><div class="n">{fav_count}</div><div class="l">Saved properties</div></div>
</div>
<div class="sec-head"><h2>My enquiries</h2><a class="btn btn-brass btn-sm" href="/properties">Browse more</a></div>
<div class="table-wrap"><table class="data">
  <thead><tr><th>Property</th><th>City</th><th>Message</th><th>Status</th><th>Sent</th></tr></thead>
  <tbody>{rows}</tbody>
</table></div>
"""
    return Response(layout("My Account", body, req))


def saved(req):
    conn = get_conn()
    rows = conn.execute(
        "SELECT p.* FROM favorites f JOIN properties p ON p.id = f.property_id "
        "WHERE f.user_id = ? ORDER BY f.created_at DESC", (req.user["id"],)).fetchall()
    fav_ids = {p["id"] for p in rows}
    conn.close()
    cards = "".join(prop_card(p, fav_ids) for p in rows) or \
        '<div class="empty">No saved properties yet. Tap ☆ on any listing to save it.</div>'
    body = f"""
<p class="eyebrow">Customer panel</p>
<h1>Saved properties</h1>
<div class="prop-grid" style="margin-top:1.5rem">{cards}</div>
"""
    return Response(layout("Saved", body, req))


def toggle_favorite(req, pid):
    conn = get_conn()
    existing = conn.execute("SELECT 1 FROM favorites WHERE user_id = ? AND property_id = ?",
                            (req.user["id"], pid)).fetchone()
    if existing:
        conn.execute("DELETE FROM favorites WHERE user_id = ? AND property_id = ?",
                     (req.user["id"], pid))
    else:
        conn.execute("INSERT OR IGNORE INTO favorites (user_id, property_id, created_at) VALUES (?,?,?)",
                     (req.user["id"], pid, now()))
    conn.commit()
    conn.close()
    ref = req.cookies.get("_ref") or "/properties"
    return redirect(ref)


# ---------------------------------------------------------------------------
# Owner (admin) panel
# ---------------------------------------------------------------------------

def owner_dashboard(req):
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) c FROM properties").fetchone()["c"]
    avail = conn.execute("SELECT COUNT(*) c FROM properties WHERE status='available'").fetchone()["c"]
    leads = conn.execute("SELECT COUNT(*) c FROM enquiries").fetchone()["c"]
    new_leads = conn.execute("SELECT COUNT(*) c FROM enquiries WHERE status='new'").fetchone()["c"]
    recent = conn.execute(
        "SELECT en.*, p.title FROM enquiries en LEFT JOIN properties p ON p.id = en.property_id "
        "ORDER BY en.created_at DESC LIMIT 6").fetchall()
    conn.close()

    rows = "".join(
        f"<tr><td>{e(en['name'])}</td><td>{e(en['title'] or '—')}</td>"
        f"<td>{e(en['email'])}</td><td><span class='pill {e(en['status'])}'>{e(en['status'])}</span></td>"
        f"<td class='tabular'>{e(en['created_at'][:10])}</td></tr>"
        for en in recent) or "<tr><td colspan='5' class='empty'>No leads yet.</td></tr>"

    body = f"""
<p class="eyebrow">Owner panel</p>
<h1>Dashboard</h1>
<div class="stat-row" style="margin-top:1.5rem">
  <div class="stat"><div class="n">{total}</div><div class="l">Total listings</div></div>
  <div class="stat"><div class="n">{avail}</div><div class="l">Available</div></div>
  <div class="stat"><div class="n">{leads}</div><div class="l">Total leads</div></div>
  <div class="stat"><div class="n">{new_leads}</div><div class="l">New leads</div></div>
</div>
<div class="sec-head"><h2>Recent leads</h2><div class="inline-actions">
  <a class="btn btn-ghost btn-sm" href="/owner/leads">All leads</a>
  <a class="btn btn-brass btn-sm" href="/owner/properties/new">+ Add property</a>
</div></div>
<div class="table-wrap"><table class="data">
  <thead><tr><th>From</th><th>Property</th><th>Email</th><th>Status</th><th>Date</th></tr></thead>
  <tbody>{rows}</tbody>
</table></div>
"""
    return Response(layout("Owner Dashboard", body, req))


def owner_properties(req):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM properties ORDER BY created_at DESC").fetchall()
    conn.close()
    trs = "".join(
        f"<tr><td>{e(p['title'])}</td><td>{e(p['ptype'])}</td><td>{e(p['city'])}</td>"
        f"<td class='tabular price'>{money(p['price'])}</td>"
        f"<td><span class='pill {e(p['status'])}'>{e(p['status'])}</span></td>"
        f"<td class='inline-actions'>"
        f"<a class='btn btn-ghost btn-sm' href='/owner/properties/{p['id']}/edit'>Edit</a>"
        f"<form method='post' action='/owner/properties/{p['id']}/delete' onsubmit=\"return confirm('Delete this listing?')\" style='display:inline'>"
        f"<button class='btn btn-danger btn-sm' type='submit'>Delete</button></form>"
        f"</td></tr>"
        for p in rows) or "<tr><td colspan='6' class='empty'>No properties yet.</td></tr>"
    body = f"""
<div class="sec-head" style="margin-top:0"><div><p class="eyebrow">Owner panel</p><h1>Properties</h1></div>
  <a class="btn btn-brass" href="/owner/properties/new">+ Add property</a></div>
<div class="table-wrap"><table class="data">
  <thead><tr><th>Title</th><th>Type</th><th>City</th><th>Price</th><th>Status</th><th>Actions</th></tr></thead>
  <tbody>{trs}</tbody>
</table></div>
"""
    return Response(layout("Manage Properties", body, req))


def _property_form(req, p=None):
    title = "Edit property" if p else "Add a property"
    action = f"/owner/properties/{p['id']}/edit" if p else "/owner/properties/new"
    g = (lambda k, d="": e(p[k]) if p else d)
    sel_status = p["status"] if p else "available"
    sel_listing = p["listing"] if p else "buy"
    feat_checked = " checked" if p and p["featured"] else ""
    body = f"""
<p><a class="muted-link" href="/owner/properties">← Back to properties</a></p>
<h1>{e(title)}</h1>
<form method="post" action="{action}" class="card" style="margin-top:1.2rem">
  <div class="form-grid">
    <div class="full"><label>Title</label><input name="title" required value="{g('title')}"></div>
    <div><label>Type</label><select name="ptype">{opts(PTYPES, p['ptype'] if p else '')}</select></div>
    <div><label>Listing</label><select name="listing">
      <option value="buy"{" selected" if sel_listing=="buy" else ""}>Buy</option>
      <option value="rent"{" selected" if sel_listing=="rent" else ""}>Rent</option></select></div>
    <div><label>City</label><select name="city">{opts(CITIES, p['city'] if p else '')}</select></div>
    <div><label>Locality</label><input name="locality" value="{g('locality')}"></div>
    <div><label>Price (₹ total / monthly rent)</label><input name="price" type="number" min="0" required value="{g('price','0')}"></div>
    <div><label>Area (sqft)</label><input name="area_sqft" type="number" min="0" value="{g('area_sqft','0')}"></div>
    <div><label>Bedrooms</label><input name="bedrooms" type="number" min="0" value="{g('bedrooms','0')}"></div>
    <div><label>Bathrooms</label><input name="bathrooms" type="number" min="0" value="{g('bathrooms','0')}"></div>
    <div><label>Status</label><select name="status">
      <option value="available"{" selected" if sel_status=="available" else ""}>Available</option>
      <option value="sold"{" selected" if sel_status=="sold" else ""}>Sold</option>
      <option value="rented"{" selected" if sel_status=="rented" else ""}>Rented</option></select></div>
    <div><label>Featured on homepage</label><label style="font-weight:400;color:var(--ink)"><input type="checkbox" name="featured" value="1" style="width:auto;margin-right:0.4rem"{feat_checked}>Highlight this listing</label></div>
    <div class="full"><label>Description</label><textarea name="description">{g('description')}</textarea></div>
  </div>
  <div style="margin-top:1.2rem"><button class="btn btn-brass" type="submit">{"Save changes" if p else "Create listing"}</button></div>
</form>
"""
    return Response(layout(title, body, req))


def owner_property_new_form(req):
    return _property_form(req)


def _collect_property(req):
    def num(k):
        try:
            return int(req.f(k) or 0)
        except ValueError:
            return 0
    return dict(
        title=req.f("title"), ptype=req.f("ptype") or "Flat", listing=req.f("listing") or "buy",
        city=req.f("city") or "Jaipur", locality=req.f("locality"), price=num("price"),
        area_sqft=num("area_sqft"), bedrooms=num("bedrooms"), bathrooms=num("bathrooms"),
        status=req.f("status") or "available", description=req.f("description"),
        featured=1 if req.f("featured") else 0)


def owner_property_create(req):
    d = _collect_property(req)
    if not d["title"]:
        return redirect("/owner/properties/new", err="Title is required.")
    conn = get_conn()
    conn.execute(
        "INSERT INTO properties (title, ptype, listing, city, locality, price, area_sqft, "
        "bedrooms, bathrooms, description, status, featured, owner_id, created_at) "
        "VALUES (:title,:ptype,:listing,:city,:locality,:price,:area_sqft,:bedrooms,"
        ":bathrooms,:description,:status,:featured,:owner_id,:created_at)",
        {**d, "owner_id": req.user["id"], "created_at": now()})
    conn.commit()
    conn.close()
    return redirect("/owner/properties", msg="Listing added to the register.")


def owner_property_edit_form(req, pid):
    conn = get_conn()
    p = conn.execute("SELECT * FROM properties WHERE id = ?", (pid,)).fetchone()
    conn.close()
    if not p:
        return not_found(req)
    return _property_form(req, p)


def owner_property_update(req, pid):
    d = _collect_property(req)
    conn = get_conn()
    if not conn.execute("SELECT 1 FROM properties WHERE id = ?", (pid,)).fetchone():
        conn.close()
        return not_found(req)
    conn.execute(
        "UPDATE properties SET title=:title, ptype=:ptype, listing=:listing, city=:city, "
        "locality=:locality, price=:price, area_sqft=:area_sqft, bedrooms=:bedrooms, "
        "bathrooms=:bathrooms, description=:description, status=:status, featured=:featured "
        "WHERE id=:id", {**d, "id": pid})
    conn.commit()
    conn.close()
    return redirect("/owner/properties", msg="Listing updated.")


def owner_property_delete(req, pid):
    conn = get_conn()
    conn.execute("DELETE FROM properties WHERE id = ?", (pid,))
    conn.commit()
    conn.close()
    return redirect("/owner/properties", msg="Listing deleted.")


def owner_leads(req):
    conn = get_conn()
    rows = conn.execute(
        "SELECT en.*, p.title FROM enquiries en LEFT JOIN properties p ON p.id = en.property_id "
        "ORDER BY en.created_at DESC").fetchall()
    conn.close()
    trs = ""
    for en in rows:
        status_form = (
            f"<form method='post' action='/owner/leads/{en['id']}/status' style='display:flex;gap:0.3rem'>"
            f"<select name='status' style='padding:0.3rem'>"
            f"<option value='new'{' selected' if en['status']=='new' else ''}>new</option>"
            f"<option value='contacted'{' selected' if en['status']=='contacted' else ''}>contacted</option>"
            f"<option value='closed'{' selected' if en['status']=='closed' else ''}>closed</option>"
            f"</select><button class='btn btn-ghost btn-sm' type='submit'>Set</button></form>")
        trs += (
            f"<tr><td>{e(en['name'])}<br><span style='color:var(--muted);font-size:0.8rem'>{e(en['email'])} · {e(en['phone'])}</span></td>"
            f"<td>{e(en['title'] or '—')}</td><td style='max-width:280px'>{e(en['message'])}</td>"
            f"<td>{status_form}</td><td class='tabular'>{e(en['created_at'][:10])}</td></tr>")
    trs = trs or "<tr><td colspan='5' class='empty'>No leads yet.</td></tr>"
    body = f"""
<p class="eyebrow">Owner panel</p>
<h1>Leads &amp; enquiries</h1>
<p class="lead" style="margin-bottom:1.5rem">{len(rows)} enquir{"y" if len(rows)==1 else "ies"} received.</p>
<div class="table-wrap"><table class="data">
  <thead><tr><th>From</th><th>Property</th><th>Message</th><th>Status</th><th>Date</th></tr></thead>
  <tbody>{trs}</tbody>
</table></div>
"""
    return Response(layout("Leads", body, req))


def owner_lead_status(req, eid):
    status = req.f("status")
    if status in ("new", "contacted", "closed"):
        conn = get_conn()
        conn.execute("UPDATE enquiries SET status = ? WHERE id = ?", (status, eid))
        conn.commit()
        conn.close()
    return redirect("/owner/leads", msg="Lead updated.")


# ---------------------------------------------------------------------------
# Callback requests
# ---------------------------------------------------------------------------

def _notify_owner(name, phone, preferred, note):
    """🔔 Instantly alert the owner on Telegram about a new callback request.
    Needs env var TELEGRAM_TOKEN (secret); OWNER_CHAT_ID defaults to Vikkas."""
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("OWNER_CHAT_ID", "8753045724")
    if not token:
        return  # alerts stay off until the bot token is configured on the host
    lines = ["📞 New callback request — realtorvikkas.com", "",
             f"👤 {name}", f"📱 {phone}"]
    if preferred:
        lines.append(f"🕐 Best time: {preferred}")
    if note:
        lines.append(f"📝 {note}")
    lines.append("\n(Reply fast — the first agent to call usually wins the deal!)")
    try:
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": "\n".join(lines)}).encode()
        urllib.request.urlopen(
            urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data),
            timeout=10)
    except Exception as ex:
        print(f"[notify] telegram alert failed: {ex}")


def submit_callback(req):
    name = (req.f("name") or "").strip()
    phone = (req.f("phone") or "").strip()
    preferred = req.f("preferred")
    note = req.f("note")
    back = req.f("back") or "/"
    if not name or not phone:
        return redirect(back, err="Please give your name and phone so we can call you back.")
    if _is_spam(name, note, req.f("website")):
        return redirect(back, msg="Thank you — Realtor Vikkas will call you back shortly.")
    conn = get_conn()
    conn.execute(
        "INSERT INTO callbacks (name, phone, preferred, note, property_id, status, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (name, phone, preferred, note, None, "new", now()))
    conn.commit()
    conn.close()
    _save_lead(name, phone, "", note or (f"Callback — best time: {preferred}" if preferred else "Callback request"))
    return redirect(back, msg="Thank you — Realtor Vikkas will call you back shortly.")


def owner_callbacks(req):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM callbacks ORDER BY created_at DESC").fetchall()
    conn.close()
    trs = ""
    for c in rows:
        status_form = (
            f"<form method='post' action='/owner/callbacks/{c['id']}/status' style='display:flex;gap:0.3rem'>"
            f"<select name='status' style='padding:0.3rem'>"
            f"<option value='new'{' selected' if c['status']=='new' else ''}>new</option>"
            f"<option value='called'{' selected' if c['status']=='called' else ''}>called</option>"
            f"<option value='done'{' selected' if c['status']=='done' else ''}>done</option>"
            f"</select><button class='btn btn-ghost btn-sm' type='submit'>Set</button></form>")
        trs += (
            f"<tr><td>{e(c['name'])}</td>"
            f"<td class='tabular'>{e(c['phone'])}</td>"
            f"<td>{e(c['preferred'] or '—')}</td>"
            f"<td style='max-width:260px'>{e(c['note'] or '')}</td>"
            f"<td>{status_form}</td><td class='tabular'>{e(c['created_at'][:10])}</td></tr>")
    trs = trs or "<tr><td colspan='6' class='empty'>No callback requests yet.</td></tr>"
    new_n = sum(1 for c in rows if c["status"] == "new")
    body = f"""
<p class="eyebrow">Owner panel</p>
<h1>📞 Callback requests</h1>
<p class="lead" style="margin-bottom:1.5rem">{len(rows)} request(s) · {new_n} awaiting a call.</p>
<div class="table-wrap"><table class="data">
  <thead><tr><th>Name</th><th>Phone</th><th>Best time</th><th>Note</th><th>Status</th><th>Date</th></tr></thead>
  <tbody>{trs}</tbody>
</table></div>
"""
    return Response(layout("Callbacks", body, req))


def owner_callback_status(req, cid):
    status = req.f("status")
    if status in ("new", "called", "done"):
        conn = get_conn()
        conn.execute("UPDATE callbacks SET status = ? WHERE id = ?", (status, cid))
        conn.commit()
        conn.close()
    return redirect("/owner/callbacks", msg="Callback updated.")


# ---------------------------------------------------------------------------
# Leads CRM + simple admin  (statuses: New | Contacted | Visited | Closed)
# ---------------------------------------------------------------------------

LEAD_STATUSES = ["New", "Contacted", "Visited", "Closed"]
ADMIN_USER = os.environ.get("ADMIN_USER") or "Vikkas@2026"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") or "Vik@1998"
_ADMIN_SECRET = (os.environ.get("SECRET_KEY") or ("realtor-admin-" + ADMIN_PASSWORD)).encode()


def _notify_lead(name, phone, prop, message):
    """🔔 Telegram alert to the owner for every new lead (enquiry or callback)."""
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("OWNER_CHAT_ID", "8753045724")
    if not token:
        return
    lines = ["🔔 New lead — realtorvikkas.com", "", f"👤 {name or '—'}", f"📱 {phone or '—'}"]
    if prop:
        lines.append(f"🏠 {prop}")
    if message:
        lines.append(f"📝 {message}")
    lines.append("\nSee all → realtorvikkas.com/admin/leads")
    try:
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": "\n".join(lines)}).encode()
        urllib.request.urlopen(
            urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data),
            timeout=10)
    except Exception as ex:  # noqa: BLE001
        print(f"[notify] telegram lead alert failed: {ex}")


def _is_spam(name, message, honeypot=""):
    """Lightweight spam filter for the public forms — a hidden honeypot field
    plus a link/HTML check. Real visitors are unaffected (the field is hidden)."""
    if (honeypot or "").strip():
        return True
    blob = (str(name) + " " + str(message)).lower()
    if "http://" in blob or "https://" in blob or "www." in blob:
        return True
    if "<a " in blob or "href=" in blob or "[url" in blob:
        return True
    return False


def _save_lead(name, phone, prop, message):
    """Record every inquiry/callback in the unified leads CRM + alert on Telegram.
    Best-effort: wrapped so a CRM hiccup can never break the enquiry/callback flow."""
    ok = False
    try:
        conn = get_conn()
        conn.execute(
            "INSERT INTO leads (name, phone, property, message, status, created) "
            "VALUES (?,?,?,?,?,?)",
            ((name or "").strip(), (phone or "").strip(), (prop or "").strip(),
             (message or "").strip(), "New", now()))
        conn.commit()
        conn.close()
        ok = True
    except Exception as ex:  # noqa: BLE001 — never let CRM break the main flow
        print(f"[leads] could not save lead: {ex}")
    if ok:
        _notify_lead(name, phone, prop, message)


def _admin_token(days=7):
    exp = int(time.time()) + days * 86400
    sig = hmac.new(_ADMIN_SECRET, f"admin.{exp}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"{exp}.{sig}"


def _admin_ok(req):
    try:
        exp, sig = req.cookies.get("admin", "").rsplit(".", 1)
        if int(exp) < int(time.time()):
            return False
        good = hmac.new(_ADMIN_SECRET, f"admin.{exp}".encode(), hashlib.sha256).hexdigest()[:32]
        return hmac.compare_digest(sig, good)
    except Exception:  # noqa: BLE001
        return False


def admin_login(req):
    if req.method == "POST":
        if req.f("username") == ADMIN_USER and req.f("password") == ADMIN_PASSWORD:
            return redirect("/admin/leads").set_cookie("admin", _admin_token(), max_age=7 * 86400)
        return redirect("/admin/login", err="Wrong username or password.")
    err = req.q("err")
    note = f'<p class="lead" style="color:#c0392b">{e(err)}</p>' if err else ""
    body = f"""
<div style="max-width:380px;margin:3rem auto">
  <p class="eyebrow">Staff only</p>
  <h1>Admin sign in</h1>
  <p class="lead" style="margin-bottom:1.2rem">Sign in to the Leads CRM.</p>
  {note}
  <form method="post" action="/admin/login" class="card" style="padding:1.5rem">
    <div style="margin-bottom:0.8rem"><label>Username</label><input name="username" required autofocus></div>
    <div style="margin-bottom:0.8rem"><label>Password</label><input name="password" type="password" required></div>
    <button class="btn btn-brass" type="submit" style="width:100%">Sign in</button>
  </form>
</div>"""
    return Response(layout("Admin sign in", body, req))


def admin_logout(req):
    return redirect("/admin/login", msg="Signed out.").set_cookie("admin", "", delete=True)


def admin_leads(req):
    if not _admin_ok(req):
        return redirect("/admin/login")
    conn = get_conn()
    rows = conn.execute("SELECT * FROM leads ORDER BY id DESC").fetchall()
    conn.close()
    trs = ""
    for l in rows:
        opts = "".join(
            f"<option value='{s}'{' selected' if l['status'] == s else ''}>{s}</option>"
            for s in LEAD_STATUSES)
        status_form = (
            f"<form method='post' action='/admin/leads/{l['id']}/status' style='display:flex;gap:0.3rem'>"
            f"<select name='status' style='padding:0.3rem'>{opts}</select>"
            f"<button class='btn btn-ghost btn-sm' type='submit'>Set</button></form>")
        when = (l["created"] or "").replace("T", " ")[:16]
        trs += (
            f"<tr><td>{e(l['name'] or '—')}</td>"
            f"<td class='tabular'>{e(l['phone'] or '—')}</td>"
            f"<td>{e(l['property'] or '—')}</td>"
            f"<td style='max-width:280px'>{e(l['message'] or '')}</td>"
            f"<td><div style='display:flex;gap:0.3rem;align-items:center'>{status_form}"
            f"<form method='post' action='/admin/leads/{l['id']}/delete' "
            f"onsubmit=\"return confirm('Delete this lead permanently?')\">"
            f"<button class='btn btn-ghost btn-sm' type='submit' title='Delete' "
            f"style='color:#c0392b'>✕</button></form></div></td>"
            f"<td class='tabular'>{e(when)}</td></tr>")
    trs = trs or "<tr><td colspan='6' class='empty'>No leads yet.</td></tr>"
    new_n = sum(1 for l in rows if l["status"] == "New")
    body = f"""
<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem">
  <div><p class="eyebrow">Admin</p><h1>📇 Leads CRM</h1></div>
  <a class="btn btn-ghost btn-sm" href="/admin/logout">Log out</a>
</div>
<p class="lead" style="margin-bottom:1.5rem">{len(rows)} lead(s) · {new_n} new · latest first.</p>
<div class="table-wrap"><table class="data">
  <thead><tr><th>Name</th><th>Phone</th><th>Property</th><th>Message</th><th>Status</th><th>Date</th></tr></thead>
  <tbody>{trs}</tbody>
</table></div>
"""
    return Response(layout("Leads · Admin", body, req))


def admin_lead_status(req, lead_id):
    if not _admin_ok(req):
        return redirect("/admin/login")
    st = req.f("status")
    if st in LEAD_STATUSES:
        conn = get_conn()
        conn.execute("UPDATE leads SET status = ? WHERE id = ?", (st, lead_id))
        conn.commit()
        conn.close()
    return redirect("/admin/leads", msg="Lead updated.")


def admin_lead_delete(req, lead_id):
    if not _admin_ok(req):
        return redirect("/admin/login")
    conn = get_conn()
    conn.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
    conn.commit()
    conn.close()
    return redirect("/admin/leads", msg="Lead deleted.")


def api_leads(req):
    """JSON feed of recent leads for JARVIS. Auth: ?key= must equal SYNC_KEY."""
    if req.q("key") != SYNC_KEY:
        return Response(json.dumps({"ok": False, "error": "unauthorized"}),
                        status=401, content_type="application/json")
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, name, phone, property, message, status, created "
        "FROM leads ORDER BY id DESC LIMIT 30").fetchall()
    conn.close()
    leads = [dict(r) for r in rows]
    return Response(json.dumps({"ok": True, "count": len(leads), "leads": leads}),
                    content_type="application/json")


# ---------------------------------------------------------------------------
# Investment / resort module (Phase 3)
# ---------------------------------------------------------------------------

def _ticket_label(n):
    try:
        return money(n) if int(n) > 0 else "On request"
    except (TypeError, ValueError):
        return "On request"


def _invest_highlights(iv):
    raw = iv["highlights"] if "highlights" in iv.keys() else ""
    return [h.strip() for h in str(raw or "").replace("\n", ",").split(",") if h.strip()]


_INV_SVG = ('<svg width="46" height="46" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="1.3" aria-hidden="true"><path d="M3 21h18M5 21V10l7-5 7 5v11"/>'
            '<path d="M9 21v-6h6v6"/></svg>')


def _invest_card(iv):
    photos = _photo_list(iv["photos_url"])
    if photos:
        media = (f'<img src="{e(photos[0])}" alt="{e(iv["category"])} — {e(iv["location"] or "Jaipur")}" '
                 f'loading="lazy" style="width:100%;height:100%;object-fit:cover">')
    else:
        media = _INV_SVG
    hl = _invest_highlights(iv)[:3]
    hl_html = ("<ul class='inv-hl'>" + "".join(f"<li>{e(h)}</li>" for h in hl) + "</ul>") if hl else ""
    return f"""<article class="inv-card">
  <div class="inv-vignette"><span class="inv-badge">{e(iv["category"])}</span>{media}</div>
  <div class="inv-body">
    <h3><a href="/invest/{iv["id"]}">{e(iv["title"])}</a></h3>
    <div class="inv-loc">{e(iv["location"] or "Jaipur")}</div>
    {hl_html}
    <div class="inv-foot">
      <span class="inv-ticket">{e(_ticket_label(iv["ticket"]))}</span>
      <a class="pa-btn view" href="/invest/{iv["id"]}">Details</a>
    </div>
  </div>
</article>"""


def _consult_form(opp=""):
    """Investment consultation form → POST /invest/enquiry → the unified leads CRM."""
    budgets = ["Under ₹25 L", "₹25 L – ₹50 L", "₹50 L – ₹1 Cr", "₹1 – 2 Cr", "₹2 Cr +", "Flexible"]
    goals = ["Capital appreciation", "Rental income", "Second home / holiday",
             "Resort / farmhouse", "Not sure yet"]
    bopts = "".join(f'<option>{e(b)}</option>' for b in budgets)
    gopts = "".join(f'<option>{e(g)}</option>' for g in goals)
    return f"""<form method="post" action="/invest/enquiry" class="card consult-form">
  <input type="hidden" name="opp" value="{e(opp)}">
  <input type="text" name="website" tabindex="-1" autocomplete="off" aria-hidden="true" style="position:absolute!important;left:-9999px!important;top:-9999px!important;height:1px;width:1px;opacity:0">
  <div class="consult-grid">
    <div><label>Name</label><input name="name" required></div>
    <div><label>Phone / WhatsApp</label><input name="phone" required placeholder="+91 …"></div>
    <div><label>Budget</label><select name="budget">{bopts}</select></div>
    <div><label>Goal</label><select name="goal">{gopts}</select></div>
    <div><label>Time horizon (optional)</label><input name="horizon" placeholder="e.g. 3–5 years"></div>
    <div><label>Preferred area (optional)</label><input name="message" placeholder="e.g. Jagatpura, Ajmer Road…"></div>
  </div>
  <button class="btn btn-brass" type="submit" style="margin-top:1rem">Request a consultation</button>
</form>"""


def invest_page(req):
    cat = req.q("category")
    conn = get_conn()
    sql = "SELECT * FROM investments WHERE status != 'hidden'"
    args = []
    if cat in INVEST_CATEGORIES:
        sql += " AND category = ?"; args.append(cat)
    sql += " ORDER BY featured DESC, created_at DESC"
    rows = conn.execute(sql, args).fetchall()
    conn.close()

    chips = f'<a class="chip{"" if cat in INVEST_CATEGORIES else " active"}" href="/invest">All</a>'
    for c in INVEST_CATEGORIES:
        chips += (f'<a class="chip{" active" if cat == c else ""}" '
                  f'href="/invest?category={urllib.parse.quote(c)}">{e(c)}</a>')

    cards = "".join(_invest_card(iv) for iv in rows) or (
        '<div class="empty">Current opportunities are shared privately. '
        '<a href="#consult">Request a consultation</a> and Realtor Vikkas will send a shortlist '
        'matched to your goals.</div>')

    wa = _wa_url("Hi, I'd like an investment consultation for property in Jaipur. Please guide me.")
    steps = [
        ("1", "Consultation", "We understand your goal, budget and time horizon — no obligation."),
        ("2", "Curated shortlist", "You get opportunities matched to you, not a generic list."),
        ("3", "Due diligence", "Title, approvals, JDA/RERA and paperwork checked before you commit."),
        ("4", "Invest &amp; manage", "Registry, and ongoing resale or rental support if you need it."),
    ]
    steps_html = "".join(
        f'<div class="step"><span class="step-n">{n}</span><h3>{t}</h3><p>{d}</p></div>'
        for n, t, d in steps)

    body = f"""
<p class="eyebrow">Investment &amp; Resorts · Jaipur</p>
<h1>Invest in Jaipur real estate — with guidance, not guesswork</h1>
<p class="lead">Plots, pre-launch homes, rental-yield commercial and resort / second-home opportunities
in and around Jaipur — shortlisted, checked and explained by Realtor Vikkas so you invest with a
clear picture. No hype, no guaranteed-return promises.</p>
<div class="detail-actions">
  <a class="da-btn wa" href="{wa}" target="_blank" rel="noopener">💬 Free consultation</a>
  <a class="da-btn call" href="tel:{PHONE}">📞 Call Now</a>
  <a class="da-btn visit" href="#consult">📝 Share your goals</a>
</div>

<div class="chips" style="margin:1.6rem 0">{chips}</div>
<div class="inv-grid">{cards}</div>

<section class="detail-section">
  <h2>How it works</h2>
  <div class="steps">{steps_html}</div>
</section>

<section class="detail-section" id="consult">
  <h2>Request an investment consultation</h2>
  <p class="lead" style="margin-bottom:1rem">Tell Realtor Vikkas what you're looking for — you'll
  get a call back and a shortlist. Your details are private.</p>
  {_consult_form()}
</section>

<p class="disclaimer">{INVEST_DISCLAIMER}</p>
"""
    seo_title = "Property Investment & Resorts in Jaipur — Realtor Vikkas"
    seo_desc = ("Invest in Jaipur real estate — plots, pre-launch homes, rental-yield commercial and "
                "resort / second-home opportunities, shortlisted and due-diligence-checked by Realtor "
                "Vikkas. Request a free, no-obligation consultation.")
    return Response(layout(seo_title, body, req, description=seo_desc,
                           canonical=SITE_BASE + "/invest"))


def invest_detail(req, iid):
    conn = get_conn()
    iv = conn.execute("SELECT * FROM investments WHERE id = ?", (iid,)).fetchone()
    if not iv or iv["status"] == "hidden":
        conn.close()
        return not_found(req)
    similar = conn.execute(
        "SELECT * FROM investments WHERE status != 'hidden' AND id != ? AND category = ? "
        "ORDER BY featured DESC, created_at DESC LIMIT 3", (iid, iv["category"])).fetchall()
    conn.close()

    photos = _photo_list(iv["photos_url"])
    banner = _gallery(photos, f'{e(iv["category"])} — {e(iv["location"] or "Jaipur")}') if photos \
        else f'<div class="detail-banner">{_INV_SVG}</div>'
    hl = _invest_highlights(iv)
    hl_html = ("<ul class='amenities'>" + "".join(f"<li class='amenity'>{e(h)}</li>" for h in hl)
               + "</ul>") if hl else ""
    horizon_row = (f'<div><div class="k">Indicative horizon</div><div class="v">{e(iv["horizon"])}</div></div>'
                   if iv["horizon"] else "")
    _url = f'{SITE_BASE}/invest/{iv["id"]}'
    wa = _wa_url(f'Hi, I am interested in the investment opportunity "{iv["title"]}" '
                 f'({iv["location"] or "Jaipur"}) — {_url}. Please share details.')
    sim_html = ""
    if similar:
        sim_html = ('<section class="detail-section"><h2>More ' + e(iv["category"]) + ' opportunities</h2>'
                    '<div class="inv-grid">' + "".join(_invest_card(s) for s in similar) + "</div></section>")
    qr_svg = _qr_svg(_url)
    qr_card = (f'<div class="card qr-card"><h3 style="font-size:1.05rem;margin-bottom:.3rem">Scan &amp; share</h3>'
               f'<div class="qr-box">{qr_svg}</div></div>') if qr_svg else ""

    body = f"""
<p><a class="muted-link" href="/invest">← Back to investments</a></p>
<div class="detail-head">
  <div>
    {banner}
    <p class="eyebrow" style="margin-top:1.2rem">Investment · {e(iv["category"])}</p>
    <h1>{e(iv["title"])}</h1>
    <p class="lead">{e(iv["location"] or "Jaipur")}</p>
    <div class="spec-list">
      <div><div class="k">Ticket size</div><div class="v price">{e(_ticket_label(iv["ticket"]))}</div></div>
      <div><div class="k">Category</div><div class="v">{e(iv["category"])}</div></div>
      {horizon_row}
    </div>
    <div class="detail-actions">
      <a class="da-btn wa" href="{wa}" target="_blank" rel="noopener">💬 WhatsApp</a>
      <a class="da-btn call" href="tel:{PHONE}">📞 Call Now</a>
      <a class="da-btn visit" href="#consult">📝 Request consultation</a>
    </div>
    {"<h2 style='font-size:1.15rem;margin:1.6rem 0 .5rem'>Highlights</h2>" + hl_html if hl_html else ""}
    <p style="margin-top:1rem">{e(iv["description"])}</p>
  </div>
  <aside>
    <div class="card" id="consult">
      <h3 style="font-size:1.2rem;margin-bottom:0.3rem">Request a consultation</h3>
      <p class="lead" style="font-size:0.85rem;margin-bottom:1rem">Realtor Vikkas will call you back about this opportunity.</p>
      {_consult_form(iv["title"])}
    </div>
    {qr_card}
  </aside>
</div>
<p class="disclaimer">{INVEST_DISCLAIMER}</p>
{sim_html}
"""
    seo_title = f'{iv["title"]} — Investment in {iv["location"] or "Jaipur"} | Realtor Vikkas'
    seo_desc = (f'{iv["category"]} investment opportunity in {iv["location"] or "Jaipur"}. '
                + (iv["description"][:150].strip() if iv["description"] else "")).strip()
    return Response(layout(seo_title, body, req, description=seo_desc,
                           canonical=SITE_BASE + f"/invest/{iv['id']}"))


def invest_enquiry(req):
    name, phone = req.f("name"), req.f("phone")
    budget, goal = req.f("budget"), req.f("goal")
    horizon, msg, opp = req.f("horizon"), req.f("message"), req.f("opp")
    thanks = "Thank you — Realtor Vikkas will reach out about your investment goals."
    if _is_spam(name, msg, req.f("website")):
        return redirect("/invest", msg=thanks)          # silently drop spam
    parts = []
    if budget:  parts.append(f"Budget: {budget}")
    if goal:    parts.append(f"Goal: {goal}")
    if horizon: parts.append(f"Horizon: {horizon}")
    if msg:     parts.append(f"Area: {msg}")
    full = " · ".join(parts) if parts else "Investment consultation request"
    prop = f"Investment: {opp}" if opp else "Investment consultation"
    _save_lead(name, phone, prop, full)
    return redirect("/invest", msg=thanks)


# ---- Admin: investment opportunities CRUD (same password admin as leads) ----

def admin_investments(req):
    if not _admin_ok(req):
        return redirect("/admin/login")
    if req.method == "POST":
        title = req.f("title")
        if title:
            conn = get_conn()
            conn.execute(
                "INSERT INTO investments (title, category, location, ticket, horizon, highlights, "
                "description, photos_url, status, featured, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (title, req.f("category") or "Plot", req.f("location"),
                 _sync_int(req.f("ticket")) or 0, req.f("horizon"), req.f("highlights"),
                 req.f("description"), req.f("photos_url"), "active",
                 1 if req.f("featured") else 0, now()))
            conn.commit()
            conn.close()
        return redirect("/admin/investments", msg="Investment opportunity added.")

    conn = get_conn()
    rows = conn.execute("SELECT * FROM investments ORDER BY id DESC").fetchall()
    conn.close()
    trs = ""
    for iv in rows:
        toggle = "hidden" if iv["status"] != "hidden" else "active"
        tlabel = "Hide" if iv["status"] != "hidden" else "Show"
        trs += (
            f"<tr><td>{e(iv['title'])}</td><td>{e(iv['category'])}</td>"
            f"<td>{e(iv['location'] or '—')}</td><td class='tabular'>{e(_ticket_label(iv['ticket']))}</td>"
            f"<td>{e(iv['status'])}</td>"
            f"<td><div style='display:flex;gap:0.3rem;align-items:center'>"
            f"<a class='btn btn-ghost btn-sm' href='/invest/{iv['id']}' target='_blank'>View</a>"
            f"<form method='post' action='/admin/investments/{iv['id']}/status'>"
            f"<input type='hidden' name='to' value='{toggle}'>"
            f"<button class='btn btn-ghost btn-sm' type='submit'>{tlabel}</button></form>"
            f"<form method='post' action='/admin/investments/{iv['id']}/delete' "
            f"onsubmit=\"return confirm('Delete this opportunity permanently?')\">"
            f"<button class='btn btn-ghost btn-sm' type='submit' style='color:#c0392b'>✕</button></form>"
            f"</div></td></tr>")
    trs = trs or "<tr><td colspan='6' class='empty'>No opportunities yet.</td></tr>"
    catopts = opts(INVEST_CATEGORIES)
    body = f"""
<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem">
  <div><p class="eyebrow">Admin</p><h1>💼 Investment opportunities</h1></div>
  <a class="btn btn-ghost btn-sm" href="/admin/logout">Log out</a>
</div>
<p class="lead" style="margin-bottom:1.2rem">{len(rows)} opportunit{"y" if len(rows)==1 else "ies"}. Add real ones here — leave prices blank to show “On request”. Do not enter guaranteed returns.</p>

<form method="post" action="/admin/investments" class="card" style="margin-bottom:1.6rem">
  <div class="consult-grid">
    <div><label>Title *</label><input name="title" required placeholder="e.g. JDA-approved plots, Ajmer Road"></div>
    <div><label>Category</label><select name="category">{catopts}</select></div>
    <div><label>Location</label><input name="location" placeholder="Area, Jaipur"></div>
    <div><label>Ticket size ₹ (blank = On request)</label><input name="ticket" inputmode="numeric" placeholder="e.g. 8500000"></div>
    <div><label>Indicative horizon (optional)</label><input name="horizon" placeholder="e.g. 3–5 years"></div>
    <div><label>Photos URL(s), comma-separated</label><input name="photos_url" placeholder="https://…"></div>
  </div>
  <div style="margin-top:0.8rem"><label>Highlights (comma-separated)</label><input name="highlights" placeholder="JDA-approved, Clear title, Corner plot"></div>
  <div style="margin-top:0.8rem"><label>Description</label><textarea name="description" placeholder="Factual details. No guaranteed returns."></textarea></div>
  <label style="display:flex;align-items:center;gap:0.4rem;margin-top:0.8rem;font-size:0.85rem"><input type="checkbox" name="featured" value="1" style="width:auto"> Feature on top</label>
  <button class="btn btn-brass" type="submit" style="margin-top:1rem">Add opportunity</button>
</form>

<div class="table-wrap"><table class="data">
  <thead><tr><th>Title</th><th>Category</th><th>Location</th><th>Ticket</th><th>Status</th><th>Actions</th></tr></thead>
  <tbody>{trs}</tbody>
</table></div>
"""
    return Response(layout("Investments · Admin", body, req))


def admin_invest_status(req, iid):
    if not _admin_ok(req):
        return redirect("/admin/login")
    to = req.f("to")
    if to in ("active", "hidden"):
        conn = get_conn()
        conn.execute("UPDATE investments SET status = ? WHERE id = ?", (to, iid))
        conn.commit()
        conn.close()
    return redirect("/admin/investments", msg="Updated.")


def admin_invest_delete(req, iid):
    if not _admin_ok(req):
        return redirect("/admin/login")
    conn = get_conn()
    conn.execute("DELETE FROM investments WHERE id = ?", (iid,))
    conn.commit()
    conn.close()
    return redirect("/admin/investments", msg="Opportunity deleted.")


# ---------------------------------------------------------------------------
# Property comparison (Phase 5)
# ---------------------------------------------------------------------------

# Tray + client logic (localStorage). Plain string (no f) so JS braces stay literal.
_COMPARE_ASSETS = """
<div id="cmpTray" class="cmp-tray" hidden>
  <span class="cmp-count"></span>
  <a class="btn btn-brass btn-sm" id="cmpGo" href="/compare">Compare</a>
  <button class="btn btn-ghost btn-sm" type="button" onclick="cmpClear()">Clear</button>
</div>
<script>
(function(){
  function get(){try{return JSON.parse(localStorage.getItem('rvCompare')||'[]')}catch(e){return[]}}
  function set(a){localStorage.setItem('rvCompare',JSON.stringify(a.slice(0,4)));render()}
  window.cmpToggle=function(id){var a=get();id=String(id);var i=a.indexOf(id);
    if(i>=0){a.splice(i,1)}else{if(a.length>=4){alert('You can compare up to 4 at a time.');return}a.push(id)}set(a)};
  window.cmpClear=function(){set([])};
  function render(){var a=get();
    document.querySelectorAll('.cmp-toggle').forEach(function(b){
      b.classList.toggle('on',a.indexOf(b.getAttribute('data-cmp'))>=0)});
    var t=document.getElementById('cmpTray');if(!t)return;
    if(a.length){t.hidden=false;t.querySelector('.cmp-count').textContent=a.length+' selected';
      document.getElementById('cmpGo').href='/compare?ids='+a.join(',')}else{t.hidden=true}}
  document.addEventListener('DOMContentLoaded',render);render();
})();
</script>"""


def _compare_toggle_btn(pid):
    return (f'<button type="button" class="cmp-toggle" data-cmp="{pid}" '
            f'onclick="cmpToggle({pid})" aria-label="Add to compare" title="Add to compare">⇄ Compare</button>')


def _amenities_inline(p):
    raw = p["amenities"] if "amenities" in p.keys() else ""
    items = [a.strip() for a in str(raw or "").replace("\n", ",").split(",") if a.strip()]
    return ", ".join(items) if items else "—"


def compare_page(req):
    ids, seen = [], set()
    for tok in (req.q("ids") or "").split(","):
        tok = tok.strip()
        if tok.isdigit() and int(tok) not in seen:
            seen.add(int(tok)); ids.append(int(tok))
    ids = ids[:4]
    conn = get_conn()
    props = []
    for pid in ids:
        p = conn.execute("SELECT * FROM properties WHERE id=? AND status!='hidden'", (pid,)).fetchone()
        if p:
            props.append(p)
    conn.close()

    if len(props) < 2:
        body = f"""
<p class="eyebrow">Compare</p>
<h1>Compare properties side by side</h1>
<p class="lead">Pick at least two listings to compare. On the
<a href="/properties">listings page</a>, tap <b>⇄ Compare</b> on any property, then open Compare.</p>
{_COMPARE_ASSETS}
"""
        return Response(layout("Compare properties", body, req,
                               description="Compare Jaipur property listings side by side.",
                               canonical=SITE_BASE + "/compare"))

    def psqft(p):
        return (f'₹{int(p["price"]/p["area_sqft"]):,}'
                if p["listing"] == "buy" and p["price"] and p["area_sqft"] else "—")

    def head(p):
        photos = _photo_list(p["photos_url"])
        thumb = (f'<img src="{e(photos[0])}" alt="" style="width:100%;height:84px;object-fit:cover;border-radius:6px">'
                 if photos else '<div class="cmp-noimg" aria-hidden="true">🏠</div>')
        return (f'{thumb}<a href="/property/{p["id"]}" class="cmp-title">{e(p["title"])}</a>')

    def actions(p):
        wa = _wa_url(f'Hi, I am interested in {p["title"]} — {SITE_BASE}/property/{p["id"]}. Please share details.')
        return (f'<a class="pa-btn view" href="/property/{p["id"]}">View</a>'
                f'<a class="pa-btn wa" href="{wa}" target="_blank" rel="noopener">WhatsApp</a>')

    rows = [
        ("Price", [f'<span class="price">{money(p["price"])}{"/mo" if p["listing"]=="rent" else ""}</span>' for p in props]),
        ("Price / sqft", [psqft(p) for p in props]),
        ("Type", [e(p["ptype"]) for p in props]),
        ("For", [e(p["listing"].title()) for p in props]),
        ("Bedrooms", [str(p["bedrooms"] or "—") for p in props]),
        ("Bathrooms", [str(p["bathrooms"] or "—") for p in props]),
        ("Area (sqft)", [str(p["area_sqft"] or "—") for p in props]),
        ("Locality", [e(p["locality"] or p["city"]) for p in props]),
        ("Status", [f'<span class="pill {e(p["status"])}">{e(p["status"])}</span>' for p in props]),
        ("Amenities", [e(_amenities_inline(p)) for p in props]),
    ]
    thead = '<tr><th class="cmp-lbl"></th>' + "".join(f'<th>{head(p)}</th>' for p in props) + "</tr>"
    tbody = ""
    for label, cells in rows:
        tbody += f'<tr><td class="cmp-lbl">{label}</td>' + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"
    tbody += ('<tr><td class="cmp-lbl">Enquire</td>'
              + "".join(f'<td><div class="prop-actions">{actions(p)}</div></td>' for p in props) + "</tr>")

    body = f"""
<p class="eyebrow">Compare</p>
<h1>Comparing {len(props)} properties</h1>
<p class="lead">Side by side, so you can weigh them at a glance.</p>
<div class="table-wrap"><table class="data cmp-table"><thead>{thead}</thead><tbody>{tbody}</tbody></table></div>
<p style="margin-top:1rem"><a class="btn btn-ghost btn-sm" href="/properties">← Back to listings</a></p>
{_COMPARE_ASSETS}
"""
    return Response(layout("Compare properties", body, req,
                           description="Compare Jaipur property listings side by side — price, area, BHK and amenities.",
                           canonical=SITE_BASE + "/compare"))


# ---------------------------------------------------------------------------
# EMI calculator (Phase 5) — deterministic math on the visitor's own inputs
# ---------------------------------------------------------------------------

_EMI_JS = """
<script>
(function(){
  function inr(n){n=Math.round(n||0);return '\\u20B9'+n.toLocaleString('en-IN')}
  function g(id){return document.getElementById(id)}
  function calc(){
    var P=parseFloat(g('emiAmt').value)||0;
    var r=(parseFloat(g('emiRate').value)||0)/12/100;
    var n=(parseFloat(g('emiYears').value)||0)*12;
    var emi = (r>0&&n>0)? P*r*Math.pow(1+r,n)/(Math.pow(1+r,n)-1) : (n>0? P/n : 0);
    var total=emi*n, interest=total-P;
    g('emiEMI').textContent = (P&&n)? inr(emi) : '\\u2014';
    g('emiP').textContent = inr(P);
    g('emiI').textContent = (P&&n)? inr(interest) : '\\u2014';
    g('emiT').textContent = (P&&n)? inr(total) : '\\u2014';
    var pi = total>0? (P/total*100) : 50;
    g('emiBarP').style.width=pi+'%'; g('emiBarI').style.width=(100-pi)+'%';
  }
  ['emiAmt','emiRate','emiYears'].forEach(function(id){g(id).addEventListener('input',calc)});
  calc();
})();
</script>"""


def emi_page(req):
    amt = _pos_int(req.q("amount")) or ""
    body = f"""
<p class="eyebrow">Tools · EMI Calculator</p>
<h1>Home-loan EMI calculator</h1>
<p class="lead">Estimate your monthly instalment. It's all worked out on your device from the numbers you enter — nothing is sent anywhere.</p>
<div class="emi-wrap">
  <form class="card emi-form" onsubmit="return false">
    <label>Loan amount (₹)</label>
    <input id="emiAmt" type="number" min="0" step="10000" value="{amt}" placeholder="e.g. 5000000">
    <label>Interest rate (% per year)</label>
    <input id="emiRate" type="number" min="0" step="0.05" value="8.5">
    <label>Tenure (years)</label>
    <input id="emiYears" type="number" min="1" max="40" step="1" value="20">
  </form>
  <div class="card emi-out">
    <div class="emi-headline"><span class="k">Monthly EMI</span><span class="v price" id="emiEMI">—</span></div>
    <div class="emi-grid">
      <div><span class="k">Principal</span><span id="emiP">—</span></div>
      <div><span class="k">Total interest</span><span id="emiI">—</span></div>
      <div><span class="k">Total payable</span><span id="emiT">—</span></div>
    </div>
    <div class="emi-bar"><span id="emiBarP" class="barP"></span><span id="emiBarI" class="barI"></span></div>
    <div class="emi-legend"><span><i class="dotP"></i> Principal</span><span><i class="dotI"></i> Interest</span></div>
  </div>
</div>
<p class="disclaimer">{EMI_DISCLAIMER}</p>
{_EMI_JS}
"""
    return Response(layout("EMI Calculator", body, req,
                           description="Free home-loan EMI calculator for Jaipur property buyers — monthly instalment, total interest and payable.",
                           canonical=SITE_BASE + "/emi"))


# ---------------------------------------------------------------------------
# Market insights / guides (Phase 5)
# ---------------------------------------------------------------------------

def _insight_card(a):
    tag = e(a["category"]) + (f' · {e(a["area"])}' if a["area"] else "")
    return f"""<article class="ins-card">
  <span class="ins-cat">{tag}</span>
  <h3><a href="/insights/{a["id"]}">{e(a["title"])}</a></h3>
  <p>{e(a["summary"] or "")}</p>
  <a class="muted-link" href="/insights/{a["id"]}">Read →</a>
</article>"""


def _insight_body_html(body):
    blocks = [b for b in str(body or "").split("\n\n") if b.strip()]
    return "".join(f"<p>{e(b).replace(chr(10), '<br>')}</p>" for b in blocks)


def insights_page(req):
    cat = req.q("category")
    conn = get_conn()
    sql = "SELECT * FROM insights WHERE status != 'hidden'"
    args = []
    if cat in INSIGHT_CATEGORIES:
        sql += " AND category = ?"; args.append(cat)
    sql += " ORDER BY featured DESC, created_at DESC"
    rows = conn.execute(sql, args).fetchall()
    conn.close()

    chips = f'<a class="chip{"" if cat in INSIGHT_CATEGORIES else " active"}" href="/insights">All</a>'
    for c in INSIGHT_CATEGORIES:
        chips += (f'<a class="chip{" active" if cat == c else ""}" '
                  f'href="/insights?category={urllib.parse.quote(c)}">{e(c)}</a>')
    wa = _wa_url("Hi, I'd like guidance on the Jaipur property market. Please help.")
    cards = "".join(_insight_card(a) for a in rows) or (
        '<div class="empty">Fresh insights are on the way. Meanwhile, '
        f'<a href="{wa}" target="_blank" rel="noopener">ask Realtor Vikkas directly</a>.</div>')
    body = f"""
<p class="eyebrow">Insights · Jaipur</p>
<h1>Market insights &amp; buyer guides</h1>
<p class="lead">Plain-English guidance on buying, renting and investing in Jaipur — title checks,
JDA approvals, and how to weigh a decision. Factual help, no hype.</p>
<div class="chips" style="margin:1.4rem 0">{chips}</div>
<div class="ins-grid">{cards}</div>
"""
    return Response(layout("Market Insights", body, req,
                           description="Jaipur real-estate insights and buyer guides from Realtor Vikkas — title checks, JDA approvals, buy vs rent.",
                           canonical=SITE_BASE + "/insights"))


def insight_detail(req, iid):
    conn = get_conn()
    a = conn.execute("SELECT * FROM insights WHERE id = ?", (iid,)).fetchone()
    if not a or a["status"] == "hidden":
        conn.close()
        return not_found(req)
    more = conn.execute(
        "SELECT * FROM insights WHERE status != 'hidden' AND id != ? "
        "ORDER BY featured DESC, created_at DESC LIMIT 3", (iid,)).fetchall()
    conn.close()
    src = f'<p class="lead" style="font-size:.82rem;margin-top:1.5rem">Source: {e(a["source"])}</p>' if a["source"] else ""
    tag = e(a["category"]) + (f' · {e(a["area"])}' if a["area"] else "")
    wa = _wa_url(f'Hi, I read "{a["title"]}" on realtorvikkas.com and would like to discuss.')
    more_html = ""
    if more:
        more_html = ('<section class="detail-section"><h2>More insights</h2><div class="ins-grid">'
                     + "".join(_insight_card(x) for x in more) + "</div></section>")
    body = f"""
<p><a class="muted-link" href="/insights">← All insights</a></p>
<p class="eyebrow" style="margin-top:1rem">{tag}</p>
<h1>{e(a["title"])}</h1>
<p class="lead">{e(a["summary"] or "")}</p>
<div class="article">{_insight_body_html(a["body"])}</div>
{src}
<div class="detail-actions" style="margin-top:1.6rem">
  <a class="da-btn wa" href="{wa}" target="_blank" rel="noopener">💬 Ask Realtor Vikkas</a>
  <a class="da-btn call" href="tel:{PHONE}">📞 Call Now</a>
</div>
{more_html}
"""
    return Response(layout(a["title"], body, req,
                           description=(a["summary"] or a["title"]),
                           canonical=SITE_BASE + f"/insights/{a['id']}"))


# ---- Admin: market insights CRUD (same password admin) ----

def admin_insights(req):
    if not _admin_ok(req):
        return redirect("/admin/login")
    if req.method == "POST":
        title = req.f("title")
        if title:
            conn = get_conn()
            conn.execute(
                "INSERT INTO insights (title, category, area, summary, body, source, status, featured, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (title, req.f("category") or "Guide", req.f("area"), req.f("summary"),
                 req.f("body"), req.f("source"), "published",
                 1 if req.f("featured") else 0, now()))
            conn.commit()
            conn.close()
        return redirect("/admin/insights", msg="Insight added.")
    conn = get_conn()
    rows = conn.execute("SELECT * FROM insights ORDER BY id DESC").fetchall()
    conn.close()
    trs = ""
    for a in rows:
        toggle = "hidden" if a["status"] != "hidden" else "published"
        tlabel = "Hide" if a["status"] != "hidden" else "Show"
        trs += (
            f"<tr><td>{e(a['title'])}</td><td>{e(a['category'])}</td><td>{e(a['area'] or '—')}</td>"
            f"<td>{e(a['status'])}</td>"
            f"<td><div style='display:flex;gap:0.3rem;align-items:center'>"
            f"<a class='btn btn-ghost btn-sm' href='/insights/{a['id']}' target='_blank'>View</a>"
            f"<form method='post' action='/admin/insights/{a['id']}/status'>"
            f"<input type='hidden' name='to' value='{toggle}'>"
            f"<button class='btn btn-ghost btn-sm' type='submit'>{tlabel}</button></form>"
            f"<form method='post' action='/admin/insights/{a['id']}/delete' "
            f"onsubmit=\"return confirm('Delete this insight permanently?')\">"
            f"<button class='btn btn-ghost btn-sm' type='submit' style='color:#c0392b'>✕</button></form>"
            f"</div></td></tr>")
    trs = trs or "<tr><td colspan='5' class='empty'>No insights yet.</td></tr>"
    body = f"""
<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem">
  <div><p class="eyebrow">Admin</p><h1>📰 Market insights</h1></div>
  <a class="btn btn-ghost btn-sm" href="/admin/logout">Log out</a>
</div>
<p class="lead" style="margin-bottom:1.2rem">{len(rows)} article(s). Add factual guidance or a real market note — never invented figures or guaranteed returns.</p>

<form method="post" action="/admin/insights" class="card" style="margin-bottom:1.6rem">
  <div class="consult-grid">
    <div><label>Title *</label><input name="title" required></div>
    <div><label>Category</label><select name="category">{opts(INSIGHT_CATEGORIES)}</select></div>
    <div><label>Area (optional)</label><input name="area" placeholder="e.g. Jagatpura, Jaipur"></div>
    <div><label>Source (optional)</label><input name="source" placeholder="e.g. JDA notification, your own data"></div>
  </div>
  <div style="margin-top:0.8rem"><label>Summary (one line)</label><input name="summary"></div>
  <div style="margin-top:0.8rem"><label>Body (blank line = new paragraph)</label><textarea name="body" rows="7"></textarea></div>
  <label style="display:flex;align-items:center;gap:0.4rem;margin-top:0.8rem;font-size:0.85rem"><input type="checkbox" name="featured" value="1" style="width:auto"> Feature on top</label>
  <button class="btn btn-brass" type="submit" style="margin-top:1rem">Publish insight</button>
</form>

<div class="table-wrap"><table class="data">
  <thead><tr><th>Title</th><th>Category</th><th>Area</th><th>Status</th><th>Actions</th></tr></thead>
  <tbody>{trs}</tbody>
</table></div>
"""
    return Response(layout("Insights · Admin", body, req))


def admin_insight_status(req, iid):
    if not _admin_ok(req):
        return redirect("/admin/login")
    to = req.f("to")
    if to in ("published", "hidden"):
        conn = get_conn()
        conn.execute("UPDATE insights SET status = ? WHERE id = ?", (to, iid))
        conn.commit()
        conn.close()
    return redirect("/admin/insights", msg="Updated.")


def admin_insight_delete(req, iid):
    if not _admin_ok(req):
        return redirect("/admin/login")
    conn = get_conn()
    conn.execute("DELETE FROM insights WHERE id = ?", (iid,))
    conn.commit()
    conn.close()
    return redirect("/admin/insights", msg="Insight deleted.")


# ---------------------------------------------------------------------------
# SEO: sitemap.xml + robots.txt
# ---------------------------------------------------------------------------

def sitemap_xml(req):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, created_at FROM properties WHERE status != 'hidden' ORDER BY id").fetchall()
    invs = conn.execute(
        "SELECT id, created_at FROM investments WHERE status != 'hidden' ORDER BY id").fetchall()
    ins = conn.execute(
        "SELECT id, created_at FROM insights WHERE status != 'hidden' ORDER BY id").fetchall()
    conn.close()

    def url(loc, priority, lastmod=None):
        lm = f"<lastmod>{lastmod}</lastmod>" if lastmod else ""
        return (f"<url><loc>{loc}</loc>{lm}"
                f"<changefreq>weekly</changefreq><priority>{priority}</priority></url>")

    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
             url(SITE_BASE + "/", "1.0"),
             url(SITE_BASE + "/properties", "0.9"),
             url(SITE_BASE + "/invest", "0.8"),
             url(SITE_BASE + "/insights", "0.7"),
             url(SITE_BASE + "/emi", "0.5"),
             url(SITE_BASE + "/terms", "0.3")]
    for r in rows:
        parts.append(url(SITE_BASE + f"/property/{r['id']}", "0.8", (r["created_at"] or "")[:10]))
    for r in invs:
        parts.append(url(SITE_BASE + f"/invest/{r['id']}", "0.7", (r["created_at"] or "")[:10]))
    for r in ins:
        parts.append(url(SITE_BASE + f"/insights/{r['id']}", "0.6", (r["created_at"] or "")[:10]))
    parts.append("</urlset>")
    return Response("".join(parts), content_type="application/xml; charset=utf-8")


def robots_txt(req):
    txt = ("User-agent: *\n"
           "Allow: /\n"
           "Disallow: /owner\n"
           "Disallow: /account\n"
           "Disallow: /admin\n"
           "Disallow: /login\n"
           "Disallow: /register\n"
           "Disallow: /api/\n\n"
           f"Sitemap: {SITE_BASE}/sitemap.xml\n")
    return Response(txt, content_type="text/plain; charset=utf-8")


# ---------------------------------------------------------------------------
# Static + errors
# ---------------------------------------------------------------------------

CONTENT_TYPES = {".css": "text/css", ".js": "application/javascript", ".png": "image/png",
                 ".jpg": "image/jpeg", ".svg": "image/svg+xml", ".ico": "image/x-icon"}


def serve_static(req, filename):
    safe = os.path.normpath(filename).lstrip("/")
    full = os.path.join(STATIC_DIR, safe)
    if not full.startswith(STATIC_DIR) or not os.path.isfile(full):
        return not_found(req)
    ext = os.path.splitext(full)[1].lower()
    with open(full, "rb") as fh:
        data = fh.read()
    # Static assets rarely change (and app.css is cache-busted with ?v=), so let
    # browsers keep them for a month — fewer round-trips on repeat visits.
    return Response(data, content_type=CONTENT_TYPES.get(ext, "application/octet-stream"),
                    headers=[("Cache-Control", "public, max-age=2592000")])


def not_found(req):
    body = '<div class="empty"><h1>404</h1><p>That page isn\'t on the register.</p>' \
           '<p><a class="btn btn-brass" href="/">Back home</a></p></div>'
    return Response(layout("Not found", body, req), status=404)


def require_role(req, role):
    if not req.user:
        return redirect("/login", err="Please log in to continue.")
    if role and req.user["role"] != role:
        return redirect("/", err="You don't have access to that area.")
    return None


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def sync_listings(req):
    """Excel → website sync. Upserts the posted properties (the Jaipur 'Live'
    rows from the control sheet) and hides every other property, so the live
    site matches the sheet. Auth: form field 'key' must equal SYNC_KEY;
    form field 'payload' is a JSON list of property dicts."""
    if req.f("key") != SYNC_KEY:
        return Response(json.dumps({"ok": False, "error": "unauthorized"}),
                        status=401, content_type="application/json")
    try:
        items = json.loads(req.f("payload") or "[]")
        assert isinstance(items, list)
    except Exception as ex:  # noqa: BLE001
        return Response(json.dumps({"ok": False, "error": f"bad payload: {ex}"}),
                        status=400, content_type="application/json")

    conn = get_conn()
    owner = conn.execute("SELECT id FROM users WHERE role='owner' ORDER BY id LIMIT 1").fetchone()
    owner_id = owner["id"] if owner else None
    live_titles, added, updated = [], 0, 0
    for it in items:
        title = str(it.get("title") or "").strip()
        if not title:
            continue
        live_titles.append(title)
        city = str(it.get("city") or "Jaipur").strip()
        locality = str(it.get("locality") or "").strip()
        ptype = str(it.get("ptype") or "Flat").strip().title()
        listing = str(it.get("listing") or "buy").strip().lower()
        photos = str(it.get("photos_url") or "").strip()
        try:
            price = int(float(it.get("price") or 0))
        except (TypeError, ValueError):
            price = 0
        # optional richer fields — only applied when the payload actually carries them
        area = _sync_int(it.get("area_sqft"))
        beds = _sync_int(it.get("bedrooms"))
        baths = _sync_int(it.get("bathrooms"))
        desc = it.get("description")
        amen = it.get("amenities")
        row = conn.execute("SELECT id FROM properties WHERE title = ?", (title,)).fetchone()
        if row:
            sets = ["ptype=?", "city=?", "locality=?", "price=?", "photos_url=?", "status='available'"]
            vals = [ptype, city, locality, price, photos]
            if area is not None:  sets.append("area_sqft=?");  vals.append(area)
            if beds is not None:  sets.append("bedrooms=?");   vals.append(beds)
            if baths is not None: sets.append("bathrooms=?");  vals.append(baths)
            if desc is not None:  sets.append("description=?"); vals.append(str(desc))
            if amen is not None:  sets.append("amenities=?");  vals.append(str(amen))
            vals.append(row["id"])
            conn.execute(f"UPDATE properties SET {', '.join(sets)} WHERE id=?", vals)
            updated += 1
        else:
            conn.execute(
                "INSERT INTO properties (title, ptype, listing, city, locality, price, "
                "area_sqft, bedrooms, bathrooms, description, status, featured, owner_id, "
                "photos_url, amenities, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (title, ptype, listing, city, locality, price, area or 0, beds or 0, baths or 0,
                 str(desc or ""), "available", 0, owner_id, photos, str(amen or ""), now()))
            added += 1

    if live_titles:
        ph = ",".join("?" * len(live_titles))
        hidden = conn.execute(
            f"UPDATE properties SET status='hidden' WHERE title NOT IN ({ph})",
            live_titles).rowcount
    else:
        hidden = 0
    conn.commit()
    live = conn.execute(
        "SELECT COUNT(*) c FROM properties WHERE status != 'hidden'").fetchone()["c"]
    conn.close()
    return Response(json.dumps({"ok": True, "added": added, "updated": updated,
                                "hidden": hidden, "live": live}),
                    content_type="application/json")


def dispatch(req):
    m, path = req.method, req.path

    # public
    if path == "/" and m == "GET":
        return home(req)
    if path == "/properties" and m == "GET":
        return list_properties(req)
    if path.startswith("/property/") and m == "GET":
        return property_detail(req, _int(path.rsplit("/", 1)[1]))
    if path == "/enquiry" and m == "POST":
        return submit_enquiry(req)
    if path == "/callback" and m == "POST":
        return submit_callback(req)
    if path == "/invest" and m == "GET":
        return invest_page(req)
    if path == "/invest/enquiry" and m == "POST":
        return invest_enquiry(req)
    if path.startswith("/invest/") and m == "GET":
        return invest_detail(req, _int(path.rsplit("/", 1)[1]))
    if path == "/compare" and m == "GET":
        return compare_page(req)
    if path == "/emi" and m == "GET":
        return emi_page(req)
    if path == "/insights" and m == "GET":
        return insights_page(req)
    if path.startswith("/insights/") and m == "GET":
        return insight_detail(req, _int(path.rsplit("/", 1)[1]))
    if path == "/api/sync-listings" and m == "POST":
        return sync_listings(req)
    if path == "/sitemap.xml" and m == "GET":
        return sitemap_xml(req)
    if path == "/robots.txt" and m == "GET":
        return robots_txt(req)
    if path.startswith("/static/") and m == "GET":
        return serve_static(req, path[len("/static/"):])

    # auth
    if path == "/login":
        return login(req) if m == "POST" else login_form(req)
    if path == "/register":
        return register(req) if m == "POST" else register_form(req)
    if path == "/logout":
        return logout(req)
    if path == "/terms":
        return terms_page(req)

    # customer panel
    if path == "/account" and m == "GET":
        return require_role(req, "customer") or account(req)
    if path == "/account/saved" and m == "GET":
        return require_role(req, "customer") or saved(req)
    if path.startswith("/favorite/") and m == "POST":
        return require_role(req, "customer") or toggle_favorite(req, _int(path.rsplit("/", 1)[1]))

    # owner panel
    if path == "/owner" and m == "GET":
        return require_role(req, "owner") or owner_dashboard(req)
    if path == "/owner/properties" and m == "GET":
        return require_role(req, "owner") or owner_properties(req)
    if path == "/owner/properties/new":
        guard = require_role(req, "owner")
        if guard:
            return guard
        return owner_property_create(req) if m == "POST" else owner_property_new_form(req)
    if path == "/owner/leads" and m == "GET":
        return require_role(req, "owner") or owner_leads(req)

    if path.startswith("/owner/properties/") and path.endswith("/edit"):
        guard = require_role(req, "owner")
        if guard:
            return guard
        pid = _int(path.split("/")[3])
        return owner_property_update(req, pid) if m == "POST" else owner_property_edit_form(req, pid)
    if path.startswith("/owner/properties/") and path.endswith("/delete") and m == "POST":
        return require_role(req, "owner") or owner_property_delete(req, _int(path.split("/")[3]))
    if path.startswith("/owner/leads/") and path.endswith("/status") and m == "POST":
        return require_role(req, "owner") or owner_lead_status(req, _int(path.split("/")[3]))
    if path == "/owner/callbacks" and m == "GET":
        return require_role(req, "owner") or owner_callbacks(req)
    if path.startswith("/owner/callbacks/") and path.endswith("/status") and m == "POST":
        return require_role(req, "owner") or owner_callback_status(req, _int(path.split("/")[3]))

    # --- Leads CRM (simple password admin) ---
    if path == "/admin/login":
        return admin_login(req)
    if path == "/admin/logout":
        return admin_logout(req)
    if path == "/admin/leads" and m == "GET":
        return admin_leads(req)
    if path.startswith("/admin/leads/") and path.endswith("/status") and m == "POST":
        return admin_lead_status(req, _int(path.split("/")[3]))
    if path.startswith("/admin/leads/") and path.endswith("/delete") and m == "POST":
        return admin_lead_delete(req, _int(path.split("/")[3]))
    if path == "/admin/investments":
        return admin_investments(req)
    if path.startswith("/admin/investments/") and path.endswith("/status") and m == "POST":
        return admin_invest_status(req, _int(path.split("/")[3]))
    if path.startswith("/admin/investments/") and path.endswith("/delete") and m == "POST":
        return admin_invest_delete(req, _int(path.split("/")[3]))
    if path == "/admin/insights":
        return admin_insights(req)
    if path.startswith("/admin/insights/") and path.endswith("/status") and m == "POST":
        return admin_insight_status(req, _int(path.split("/")[3]))
    if path.startswith("/admin/insights/") and path.endswith("/delete") and m == "POST":
        return admin_insight_delete(req, _int(path.split("/")[3]))
    if path == "/api/leads" and m == "GET":
        return api_leads(req)

    return not_found(req)


def _int(s):
    try:
        return int(s)
    except (ValueError, TypeError):
        return -1


# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "RealtorVikkas/1.0"

    def _handle(self, method):
        parsed = urllib.parse.urlparse(self.path)
        query = {k: v[-1] for k, v in urllib.parse.parse_qs(parsed.query).items()}

        form = {}
        if method == "POST":
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length).decode("utf-8") if length else ""
            form = {k: v[-1] for k, v in urllib.parse.parse_qs(raw).items()}

        cookies = {}
        if "Cookie" in self.headers:
            c = http_cookies.SimpleCookie(self.headers["Cookie"])
            cookies = {k: morsel.value for k, morsel in c.items()}

        user = auth.user_for_token(cookies.get("session"))
        req = Request(method, parsed.path, query, form, cookies, user)

        try:
            resp = dispatch(req)
        except Exception as ex:  # noqa: BLE001 - surface a friendly 500
            import traceback
            traceback.print_exc()
            resp = Response(layout("Error", f'<div class="empty"><h1>500</h1>'
                                   f'<p>Something went wrong: {e(ex)}</p></div>', req), status=500)

        # Remember last GET page so favorite toggles can bounce back to it.
        if method == "GET" and req.path in ("/properties", "/account/saved") and resp.status == 200:
            back = req.path + (("?" + parsed.query) if parsed.query else "")
            c = http_cookies.SimpleCookie()
            c["_ref"] = back
            c["_ref"]["path"] = "/"
            resp.headers.append(("Set-Cookie", c["_ref"].OutputString()))

        body = resp.body
        extra = list(resp.headers)
        # gzip text responses when the client accepts it — big transfer savings on HTML/CSS.
        ctype = resp.content_type
        compressible = ctype.startswith("text/") or any(
            t in ctype for t in ("json", "xml", "javascript", "svg"))
        accepts_gzip = "gzip" in (self.headers.get("Accept-Encoding", "") or "")
        if accepts_gzip and compressible and len(body) > 512:
            body = gzip.compress(body, 6)
            extra.append(("Content-Encoding", "gzip"))
            extra.append(("Vary", "Accept-Encoding"))

        self.send_response(resp.status)
        self.send_header("Content-Type", resp.content_type)
        self.send_header("Content-Length", str(len(body)))
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        if method != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def log_message(self, fmt, *args):
        print("  %s - %s" % (self.address_string(), fmt % args))


def main():
    try:
        init_db()
    except Exception as exc:
        # Never let a database hiccup stop the web server from starting — the
        # site must bind its port so the host routes to it instead of 404ing.
        print(f"[startup] init_db failed but continuing: {exc}")
    print(f"\n  Realtor Vikkas is running →  http://localhost:{PORT}\n")
    print("  Owner login  : thevikkas@gmail.com / Jerry@1998")
    print("  Client login : client@realtorvikkas.in / Client@1998\n")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
