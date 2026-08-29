"""SQLite storage for Realtor Vikkas.

Zero external dependencies — uses the Python standard-library sqlite3 module.
The database file (realtor.db) is created and seeded automatically on first run.
"""

import os
import sqlite3
from datetime import datetime

# Where the SQLite file lives. In production (e.g. Render with a persistent
# disk) set DATABASE_PATH to a path on that disk — e.g. /var/data/realtor.db —
# so data survives restarts and redeploys. Locally it defaults to this folder.
_LOCAL_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "realtor.db")
DB_PATH = os.environ.get("DATABASE_PATH") or _LOCAL_DB

# Ensure the folder holding the database exists. If a configured path (e.g. a
# mounted disk like /var/data) isn't available or writable, fall back to a local
# file so the app still STARTS instead of crashing at import (which would make
# the whole site return "Not Found" on the host).
try:
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
except Exception as _exc:
    print(f"[db] cannot use {DB_PATH} ({_exc}); falling back to local realtor.db")
    DB_PATH = _LOCAL_DB
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE,
    phone         TEXT    DEFAULT '',
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'customer',  -- 'owner' | 'customer'
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS properties (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    ptype       TEXT    NOT NULL,                 -- Villa | Plot | Flat | Townhouse | Commercial
    listing     TEXT    NOT NULL DEFAULT 'buy',   -- buy | rent
    city        TEXT    NOT NULL,
    locality    TEXT    DEFAULT '',
    price       INTEGER NOT NULL DEFAULT 0,       -- in INR (absolute)
    area_sqft   INTEGER DEFAULT 0,
    bedrooms    INTEGER DEFAULT 0,
    bathrooms   INTEGER DEFAULT 0,
    description TEXT    DEFAULT '',
    status      TEXT    NOT NULL DEFAULT 'available', -- available | sold | rented
    featured    INTEGER NOT NULL DEFAULT 0,
    photos_url  TEXT    DEFAULT '',
    amenities   TEXT    DEFAULT '',                   -- comma-separated (optional)
    owner_id    INTEGER,
    created_at  TEXT    NOT NULL,
    FOREIGN KEY (owner_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS enquiries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER,
    customer_id INTEGER,                          -- nullable (guest enquiries)
    name        TEXT    NOT NULL,
    email       TEXT    NOT NULL,
    phone       TEXT    DEFAULT '',
    message     TEXT    DEFAULT '',
    status      TEXT    NOT NULL DEFAULT 'new',   -- new | contacted | closed
    created_at  TEXT    NOT NULL,
    FOREIGN KEY (property_id) REFERENCES properties(id),
    FOREIGN KEY (customer_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS callbacks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    phone       TEXT    NOT NULL,
    preferred   TEXT    DEFAULT '',                -- best time to call
    note        TEXT    DEFAULT '',
    property_id INTEGER,                           -- optional (from a listing page)
    status      TEXT    NOT NULL DEFAULT 'new',    -- new | called | done
    created_at  TEXT    NOT NULL,
    FOREIGN KEY (property_id) REFERENCES properties(id)
);

CREATE TABLE IF NOT EXISTS favorites (
    user_id     INTEGER NOT NULL,
    property_id INTEGER NOT NULL,
    created_at  TEXT    NOT NULL,
    PRIMARY KEY (user_id, property_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    expires_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS leads (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT    DEFAULT '',
    phone    TEXT    DEFAULT '',
    property TEXT    DEFAULT '',
    message  TEXT    DEFAULT '',
    status   TEXT    NOT NULL DEFAULT 'New',   -- New | Contacted | Visited | Closed
    created  TEXT    NOT NULL
);
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def now():
    return datetime.utcnow().isoformat(timespec="seconds")


def init_db():
    """Create tables and seed demo data if the database is empty."""
    first_time = not os.path.exists(DB_PATH)
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()

    # migration: databases created before Excel-sync lack the photos_url column
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(properties)").fetchall()]
    if "photos_url" not in cols:
        conn.execute("ALTER TABLE properties ADD COLUMN photos_url TEXT DEFAULT ''")
        conn.commit()
    if "amenities" not in cols:                    # migration: optional amenities list
        conn.execute("ALTER TABLE properties ADD COLUMN amenities TEXT DEFAULT ''")
        conn.commit()

    # Seed only when there are no users yet, so re-runs don't duplicate data.
    have_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    if not have_users:
        _seed(conn)
    ensure_accounts(conn)          # guarantee the real owner + client logins
    conn.close()
    return first_time


# Real login accounts (owner set by Vikkas; client is a ready test account).
OWNER_EMAIL = "thevikkas@gmail.com"
OWNER_PASSWORD = "Jerry@1998"
OWNER_NAME = "Vikkas"
CLIENT_EMAIL = "client@realtorvikkas.in"
CLIENT_PASSWORD = "Client@1998"
CLIENT_NAME = "Client"


def ensure_accounts(conn):
    """Guarantee the real owner + a real client login exist. Runs on every
    start, so it also corrects an already-seeded database on a persistent disk."""
    from auth import hash_password

    owner = conn.execute(
        "SELECT id FROM users WHERE role = 'owner' ORDER BY id LIMIT 1").fetchone()
    if owner:
        conn.execute(
            "UPDATE users SET name=?, email=?, password_hash=?, role='owner' WHERE id=?",
            (OWNER_NAME, OWNER_EMAIL, hash_password(OWNER_PASSWORD), owner["id"]))
    else:
        conn.execute(
            "INSERT INTO users (name, email, phone, password_hash, role, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (OWNER_NAME, OWNER_EMAIL, "", hash_password(OWNER_PASSWORD), "owner", now()))

    client = conn.execute(
        "SELECT id FROM users WHERE role = 'customer' ORDER BY id LIMIT 1").fetchone()
    if client:
        conn.execute(
            "UPDATE users SET name=?, email=?, password_hash=?, role='customer' WHERE id=?",
            (CLIENT_NAME, CLIENT_EMAIL, hash_password(CLIENT_PASSWORD), client["id"]))
    else:
        conn.execute(
            "INSERT INTO users (name, email, phone, password_hash, role, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (CLIENT_NAME, CLIENT_EMAIL, "", hash_password(CLIENT_PASSWORD), "customer", now()))
    conn.commit()


def _seed(conn):
    # Imported here to avoid a circular import (auth imports nothing from db).
    from auth import hash_password

    owner_id = conn.execute(
        "INSERT INTO users (name, email, phone, password_hash, role, created_at) "
        "VALUES (?,?,?,?,?,?)",
        ("Vikkas", "owner@realtorvikkas.in", "+91 98290 00000",
         hash_password("vikkas123"), "owner", now()),
    ).lastrowid

    conn.execute(
        "INSERT INTO users (name, email, phone, password_hash, role, created_at) "
        "VALUES (?,?,?,?,?,?)",
        ("Aarti Sharma", "customer@example.com", "+91 90000 11111",
         hash_password("demo1234"), "customer", now()),
    )

    demo = [
        # title, ptype, listing, city, locality, price, area, bed, bath, featured, desc
        ("Aravalli Meadows Villa", "Villa", "buy", "Jaipur", "Jagatpura",
         21500000, 3200, 4, 4, 1,
         "A four-bedroom villa backing onto the Aravalli ridge, with a private lawn, staff quarter and covered parking for three cars."),
        ("Register Plot — JDA Approved", "Plot", "buy", "Jaipur", "Ajmer Road",
         8500000, 2160, 0, 0, 1,
         "JDA-approved corner plot on a 40-foot road, clear title, ready for immediate registry. Khasra verified."),
        ("Pink City Flat", "Flat", "rent", "Jaipur", "C-Scheme",
         45000, 1450, 3, 2, 0,
         "Bright 3BHK on C-Scheme's tree-lined avenue, walking distance to MI Road. Semi-furnished, lift, power backup."),
        ("Lake Vista Townhouse", "Townhouse", "buy", "Udaipur", "Fateh Sagar",
         18900000, 2400, 3, 3, 1,
         "Split-level townhouse with a rooftop terrace framing the Fateh Sagar lake. Italian marble, modular kitchen."),
        ("NCR Skyline Apartment", "Flat", "buy", "Delhi NCR", "Golf Course Ext.",
         16200000, 1720, 3, 3, 0,
         "High-floor apartment in a gated tower with clubhouse, pool and concierge. East-facing, two covered parkings."),
        ("Sabarmati Riverfront Flat", "Flat", "buy", "Ahmedabad", "Vastrapur",
         9800000, 1380, 2, 2, 0,
         "Compact 2BHK minutes from Vastrapur lake, in a well-run society with lift and 24x7 security."),
        ("Hillside Cottage", "Villa", "buy", "Shimla", "Mashobra",
         27500000, 2800, 4, 3, 1,
         "Stone-and-timber cottage on a south-facing Mashobra slope, deodar views, wood-burning fireplaces, orchard land."),
        ("Manali Apple Orchard Plot", "Plot", "buy", "Manali", "Naggar Road",
         12500000, 5400, 0, 0, 0,
         "Freehold orchard plot on Naggar Road with an existing bearing apple orchard and a mountain stream boundary."),
        ("Jodhpur Heritage Haveli", "Villa", "buy", "Jodhpur", "Old City",
         34000000, 4100, 6, 5, 0,
         "Restored sandstone haveli with a central courtyard, jharokhas and a fort-facing terrace — rare heritage title."),
        ("Gandhinagar Commercial Suite", "Commercial", "rent", "Gandhinagar", "Sector 11",
         85000, 2200, 0, 2, 0,
         "Ground-floor commercial suite on a main sector road, glass frontage, ideal for a clinic, studio or office."),
    ]
    for (title, ptype, listing, city, locality, price, area, bed, bath, feat, desc) in demo:
        conn.execute(
            "INSERT INTO properties (title, ptype, listing, city, locality, price, "
            "area_sqft, bedrooms, bathrooms, description, status, featured, owner_id, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (title, ptype, listing, city, locality, price, area, bed, bath, desc,
             "available", feat, owner_id, now()),
        )

    conn.execute(
        "INSERT INTO enquiries (property_id, customer_id, name, email, phone, message, status, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (1, 2, "Aarti Sharma", "customer@example.com", "+91 90000 11111",
         "Is the Jagatpura villa still available for a site visit this weekend?", "new", now()),
    )
    conn.commit()
