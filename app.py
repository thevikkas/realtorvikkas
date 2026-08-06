#!/usr/bin/env python3
"""Realtor Vikkas — a self-contained real-estate web app.

Standard library only. Run:  python3 app.py   then open http://localhost:8000

Public site + customer panel + owner (admin) panel, backed by SQLite.
"""

import html
import os
import re
import urllib.parse
from http import cookies as http_cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import auth
from database import get_conn, init_db, now

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(HERE, "static")
PORT = int(os.environ.get("PORT", "8000"))

CITIES = ["Jaipur", "Udaipur", "Jodhpur", "Delhi NCR", "Ahmedabad",
          "Gandhinagar", "Shimla", "Manali"]
PTYPES = ["Villa", "Plot", "Flat", "Townhouse", "Commercial"]


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

def layout(title, body, req, active=""):
    user = req.user
    if user:
        if user["role"] == "owner":
            links = ('<a href="/owner">Dashboard</a>'
                     '<a href="/owner/properties">Properties</a>'
                     '<a href="/owner/leads">Leads</a>'
                     '<a href="/properties">Public Site</a>')
        else:
            links = ('<a href="/properties">Browse</a>'
                     '<a href="/account">My Account</a>'
                     '<a href="/account/saved">Saved</a>')
        nav = (f'{links}<span class="who">{e(user["name"])} ·</span>'
               f'<a href="/logout">Log out</a>')
    else:
        nav = ('<a href="/properties">Browse</a>'
               '<a href="/login">Log in</a>'
               '<a class="btn btn-brass btn-sm" href="/register">Sign up</a>')

    flash = ""
    if req.q("msg"):
        flash += f'<div class="flash ok">{e(req.q("msg"))}</div>'
    if req.q("err"):
        flash += f'<div class="flash err">{e(req.q("err"))}</div>'

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} — Realtor Vikkas</title>
<link rel="stylesheet" href="/static/app.css">
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
</body>
</html>"""


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
    return f"""<article class="prop-card">
  <div class="prop-vignette">
    <span class="listing-badge">For {e(p["listing"])}</span>
    <svg width="52" height="40" viewBox="0 0 52 40" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M6 24 18 10l12 14"/><rect x="10" y="24" width="16" height="12"/><path d="M30 36V18l8-6 8 6v18"/></svg>
  </div>
  <div class="prop-body">
    <span class="prop-tag">{e(p["ptype"])} · {e(p["status"])}</span>
    <h3><a href="/property/{p["id"]}">{e(p["title"])}</a></h3>
    <div class="prop-loc">{e(p["locality"])}{", " if p["locality"] else ""}{e(p["city"])}</div>
    <div class="prop-specs">
      <span class="tabular">{e(spec_txt)}</span>
      <span class="price">{money(p["price"])}{"/mo" if p["listing"] == "rent" else ""} {fav}</span>
    </div>
  </div>
</article>"""


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

def home(req):
    """Serve the marketing landing page, injecting live featured listings."""
    path = os.path.join(HERE, "index.html")
    with open(path, "r", encoding="utf-8") as fh:
        return Response(fh.read())


def list_properties(req):
    city = req.q("city")
    ptype = req.q("type")
    listing = req.q("listing")
    kw = req.q("q")
    conn = get_conn()
    sql = "SELECT * FROM properties WHERE 1=1"
    args = []
    if city:
        sql += " AND city = ?"; args.append(city)
    if ptype:
        sql += " AND ptype = ?"; args.append(ptype)
    if listing:
        sql += " AND listing = ?"; args.append(listing)
    if kw:
        sql += " AND (title LIKE ? OR locality LIKE ? OR description LIKE ?)"
        args += [f"%{kw}%"] * 3
    sql += " ORDER BY featured DESC, created_at DESC"
    rows = conn.execute(sql, args).fetchall()

    fav_ids = set()
    if req.user:
        fav_ids = {r["property_id"] for r in conn.execute(
            "SELECT property_id FROM favorites WHERE user_id = ?", (req.user["id"],)).fetchall()}
    conn.close()

    cards = "".join(prop_card(p, fav_ids if req.user else None) for p in rows) or \
        '<div class="empty">No listings match those filters yet.</div>'

    body = f"""
<p class="eyebrow">The Register</p>
<h1>Browse the listings</h1>
<p class="lead">{len(rows)} propert{"y" if len(rows) == 1 else "ies"} on the register across Rajasthan, Delhi NCR, Gujarat and the Himalayas.</p>

<form class="filters" method="get" action="/properties">
  <div class="field"><label>City</label><select name="city"><option value="">All cities</option>{opts(CITIES, city)}</select></div>
  <div class="field"><label>Type</label><select name="type"><option value="">All types</option>{opts(PTYPES, ptype)}</select></div>
  <div class="field"><label>Listing</label><select name="listing"><option value="">Buy &amp; Rent</option><option value="buy"{" selected" if listing=="buy" else ""}>Buy</option><option value="rent"{" selected" if listing=="rent" else ""}>Rent</option></select></div>
  <div class="field"><label>Keyword</label><input name="q" value="{e(kw)}" placeholder="locality, project…"></div>
  <button class="btn btn-brass" type="submit">Filter</button>
  <a class="btn btn-ghost" href="/properties">Reset</a>
</form>

<div class="prop-grid">{cards}</div>
"""
    return Response(layout("Browse", body, req))


def property_detail(req, pid):
    conn = get_conn()
    p = conn.execute("SELECT * FROM properties WHERE id = ?", (pid,)).fetchone()
    if not p:
        conn.close()
        return not_found(req)
    owner = conn.execute("SELECT name, phone, email FROM users WHERE id = ?", (p["owner_id"],)).fetchone()
    conn.close()

    prefill_name = e(req.user["name"]) if req.user else ""
    prefill_email = e(req.user["email"]) if req.user else ""
    prefill_phone = e(req.user["phone"]) if req.user else ""

    body = f"""
<p><a class="muted-link" href="/properties">← Back to listings</a></p>
<div class="detail-head">
  <div>
    <div class="detail-banner">
      <svg width="90" height="70" viewBox="0 0 52 40" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M6 24 18 10l12 14"/><rect x="10" y="24" width="16" height="12"/><path d="M30 36V18l8-6 8 6v18"/></svg>
    </div>
    <p class="eyebrow" style="margin-top:1.2rem">{e(p["ptype"])} · For {e(p["listing"])}</p>
    <h1>{e(p["title"])}</h1>
    <p class="lead">{e(p["locality"])}{", " if p["locality"] else ""}{e(p["city"])}</p>
    <div class="spec-list">
      <div><div class="k">Price</div><div class="v price">{money(p["price"])}{"/mo" if p["listing"]=="rent" else ""}</div></div>
      <div><div class="k">Status</div><div class="v"><span class="pill {e(p["status"])}">{e(p["status"])}</span></div></div>
      <div><div class="k">Area</div><div class="v">{e(p["area_sqft"] or "—")} sqft</div></div>
      <div><div class="k">Bedrooms</div><div class="v">{e(p["bedrooms"] or "—")}</div></div>
      <div><div class="k">Bathrooms</div><div class="v">{e(p["bathrooms"] or "—")}</div></div>
      <div><div class="k">Listed by</div><div class="v">{e(owner["name"] if owner else "Realtor Vikkas")}</div></div>
    </div>
    <p>{e(p["description"])}</p>
  </div>

  <aside>
    <div class="card">
      <h3 style="font-size:1.2rem;margin-bottom:0.3rem">Enquire about this property</h3>
      <p class="lead" style="font-size:0.85rem;margin-bottom:1rem">Send Realtor Vikkas a message and the team will be in touch.</p>
      <form method="post" action="/enquiry">
        <input type="hidden" name="property_id" value="{p["id"]}">
        <div style="margin-bottom:0.8rem"><label>Name</label><input name="name" required value="{prefill_name}"></div>
        <div style="margin-bottom:0.8rem"><label>Email</label><input name="email" type="email" required value="{prefill_email}"></div>
        <div style="margin-bottom:0.8rem"><label>Phone</label><input name="phone" value="{prefill_phone}"></div>
        <div style="margin-bottom:0.8rem"><label>Message</label><textarea name="message" placeholder="I'd like to arrange a visit…"></textarea></div>
        <button class="btn btn-brass" type="submit" style="width:100%">Send enquiry</button>
      </form>
    </div>
  </aside>
</div>
"""
    return Response(layout(p["title"], body, req))


def submit_enquiry(req):
    pid = req.f("property_id")
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
    conn.commit()
    conn.close()
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
  <div class="demo-hint" style="margin-top:1rem">Customer demo — phone <b>90000 11111</b> / password <b>demo1234</b></div>
</div>
{PW_TOGGLE_JS}
"""
    return Response(layout("Login", body, req))


def login_form_email(req, role):
    cust_active = " is-active" if role == "customer" else ""
    own_active = " is-active" if role == "owner" else ""
    if role == "owner":
        sub = "Sign in to your owner dashboard to manage listings and leads."
        demo = 'Owner demo — <b>owner@realtorvikkas.in</b> / <b>vikkas123</b>'
        phone_switch = ""
    else:
        sub = "Sign in to browse, save and enquire on properties."
        demo = 'Customer demo — <b>customer@example.com</b> / <b>demo1234</b>'
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
    <div class="demo-hint">{demo}</div>
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
    return Response(data, content_type=CONTENT_TYPES.get(ext, "application/octet-stream"))


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

        self.send_response(resp.status)
        self.send_header("Content-Type", resp.content_type)
        self.send_header("Content-Length", str(len(resp.body)))
        for k, v in resp.headers:
            self.send_header(k, v)
        self.end_headers()
        if method != "HEAD":
            self.wfile.write(resp.body)

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def log_message(self, fmt, *args):
        print("  %s - %s" % (self.address_string(), fmt % args))


def main():
    fresh = init_db()
    if fresh:
        print("• Initialised realtor.db with demo data.")
    print(f"\n  Realtor Vikkas is running →  http://localhost:{PORT}\n")
    print("  Owner login    : owner@realtorvikkas.in / vikkas123")
    print("  Customer login : customer@example.com / demo1234\n")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
