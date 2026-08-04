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
DB_PATH = os.environ.get("DATABASE_PATH") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "realtor.db")

# Make sure the folder that will hold the database exists (matters when
# DATABASE_PATH points at a mounted disk like /var/data).
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

    # Seed only when there are no users yet, so re-runs don't duplicate data.
    have_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    if not have_users:
        _seed(conn)
    conn.close()
    return first_time


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
