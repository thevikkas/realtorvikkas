"""Password hashing and session management — standard library only.

Passwords use PBKDF2-HMAC-SHA256 with a per-user random salt.
Sessions are opaque random tokens stored server-side in the `sessions` table.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from database import get_conn

_PBKDF2_ROUNDS = 200_000
_SESSION_DAYS = 14


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds, salt, expected = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(dk.hex(), expected)
    except (ValueError, AttributeError):
        return False


# ---- Sessions ---------------------------------------------------------------

def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = (datetime.utcnow() + timedelta(days=_SESSION_DAYS)).isoformat(timespec="seconds")
    conn = get_conn()
    conn.execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (?,?,?)",
                 (token, user_id, expires))
    conn.commit()
    conn.close()
    return token


def user_for_token(token: str):
    """Return the user Row for a valid, unexpired session token, else None."""
    if not token:
        return None
    conn = get_conn()
    row = conn.execute(
        "SELECT u.*, s.expires_at FROM sessions s JOIN users u ON u.id = s.user_id "
        "WHERE s.token = ?", (token,)
    ).fetchone()
    if row is None:
        conn.close()
        return None
    if row["expires_at"] < datetime.utcnow().isoformat(timespec="seconds"):
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()
        return None
    conn.close()
    return row


def destroy_session(token: str):
    if not token:
        return
    conn = get_conn()
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()
