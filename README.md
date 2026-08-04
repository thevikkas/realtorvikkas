# Realtor Vikkas

A self-contained real-estate website — public listings, a **customer panel**, and an
**owner (admin) panel** — built on the Python standard library and SQLite. No third-party
packages, no build step.

## Run it

**Easiest — double-click:** open the `realtor-vikkas` folder in Finder and double-click
**`start.command`**. It starts the site and opens it in your browser automatically. Keep the
Terminal window that appears open while you use the site; press `Ctrl + C` (or close the
window) to stop.

**Or from the terminal:**

```bash
cd realtor-vikkas
python3 app.py
```

Then open **http://localhost:8000**. A `realtor.db` file is created and seeded with demo
listings on first run. To use a different port: `PORT=9000 python3 app.py`.

## Demo logins

| Role     | Email                     | Password   |
|----------|---------------------------|------------|
| Owner    | owner@realtorvikkas.in    | vikkas123  |
| Customer | customer@example.com      | demo1234   |

## What's inside

| File          | Purpose                                                        |
|---------------|----------------------------------------------------------------|
| `app.py`      | HTTP server, routing, page templates                           |
| `database.py` | SQLite schema + demo seed data                                 |
| `auth.py`     | PBKDF2 password hashing + server-side sessions                 |
| `index.html`  | Marketing landing page (wired into the live app)               |
| `static/`     | Shared CSS                                                      |
| `realtor.db`  | SQLite database (auto-created; safe to delete to reset)        |

## Features

**Public** — landing page, searchable/filterable listings (`/properties`), property detail
pages with an enquiry form.

**Customer panel** (`/account`) — register/login, save favourite properties, send enquiries
and track their status.

**Owner panel** (`/owner`) — dashboard stats, full add/edit/delete of listings, and a leads
inbox where enquiries can be marked *new → contacted → closed*.

## Reset the data

Stop the server and delete the database:

```bash
rm realtor.db
```

It will be re-created with fresh demo data on the next run.
