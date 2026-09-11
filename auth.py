"""Password hashing and session management — standard library only.

Passwords use PBKDF2-HMAC-SHA256 with a per-user random salt.
Sessions are opaque random tokens stored server-side in the `sessions` table.

Security Features:
  - PBKDF2-HMAC-SHA256 password hashing (200k rounds)
  - Session expiration (14 days)
  - CSRF token validation
  - Rate limiting on login attempts
  - Account lockout after 5 failed attempts
  - Automatic cleanup of expired sessions
"""

import hashlib
import hmac
import secrets
import logging
from datetime import datetime, timedelta

from database import get_conn

auth_logger = logging.getLogger("auth")

_PBKDF2_ROUNDS = 200_000
_SESSION_DAYS = 14
_SESSION_EXPIRY_HOURS = 24 * _SESSION_DAYS
_CSRF_TOKEN_SIZE = 32
_MAX_LOGIN_ATTEMPTS = 5
_LOCKOUT_MINUTES = 15


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
    """Destroy a session token."""
    if not token:
        return
    try:
        conn = get_conn()
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()
        auth_logger.info(f"Session destroyed for token: {token[:10]}...")
    except Exception as e:
        auth_logger.error(f"Error destroying session: {e}")


# ---- CSRF Protection --------------------------------------------------------

def generate_csrf_token() -> str:
    """Generate a CSRF token for form submission."""
    return secrets.token_urlsafe(_CSRF_TOKEN_SIZE)


def validate_csrf_token(token: str, expected: str) -> bool:
    """
    Validate a CSRF token using constant-time comparison.

    Args:
        token: The token to validate
        expected: The expected token

    Returns:
        True if valid, False otherwise
    """
    if not token or not expected:
        return False

    try:
        return hmac.compare_digest(token, expected)
    except Exception as e:
        auth_logger.warning(f"CSRF validation error: {e}")
        return False


# ---- Rate Limiting & Lockout ------------------------------------------------

def record_login_attempt(username: str, success: bool) -> dict:
    """
    Record a login attempt and check for lockout.

    Args:
        username: The username attempting login
        success: Whether the login succeeded

    Returns:
        {locked_out: bool, attempts: int, lockout_until: datetime}
    """
    try:
        conn = get_conn()

        # Get current attempt count
        result = conn.execute(
            "SELECT attempt_count, last_attempt_at, locked_until FROM login_attempts WHERE username = ?",
            (username,)
        ).fetchone()

        now = datetime.utcnow()

        if result is None:
            # First attempt
            if not success:
                conn.execute(
                    "INSERT INTO login_attempts (username, attempt_count, last_attempt_at) VALUES (?, ?, ?)",
                    (username, 1, now.isoformat())
                )
                conn.commit()
                conn.close()
                return {"locked_out": False, "attempts": 1, "lockout_until": None}
            else:
                # Successful login, reset attempts
                conn.close()
                return {"locked_out": False, "attempts": 0, "lockout_until": None}

        # Check if currently locked out
        if result["locked_until"]:
            lockout_until = datetime.fromisoformat(result["locked_until"])
            if now < lockout_until:
                auth_logger.warning(f"User {username} is locked out until {lockout_until}")
                conn.close()
                return {"locked_out": True, "attempts": result["attempt_count"], "lockout_until": lockout_until}
            else:
                # Lockout expired, reset
                conn.execute(
                    "UPDATE login_attempts SET attempt_count = 0, locked_until = NULL WHERE username = ?",
                    (username,)
                )
                conn.commit()

        if success:
            # Successful login, reset attempts
            conn.execute(
                "UPDATE login_attempts SET attempt_count = 0, locked_until = NULL, last_attempt_at = ? WHERE username = ?",
                (now.isoformat(), username)
            )
            auth_logger.info(f"Successful login for {username}, attempts reset")
        else:
            # Failed login, increment attempts
            new_count = result["attempt_count"] + 1
            lockout_until = None

            if new_count >= _MAX_LOGIN_ATTEMPTS:
                lockout_until = (now + timedelta(minutes=_LOCKOUT_MINUTES)).isoformat()
                auth_logger.warning(f"User {username} locked out after {new_count} failed attempts")

            conn.execute(
                "UPDATE login_attempts SET attempt_count = ?, last_attempt_at = ?, locked_until = ? WHERE username = ?",
                (new_count, now.isoformat(), lockout_until, username)
            )
            auth_logger.warning(f"Failed login for {username}, attempt {new_count}/{_MAX_LOGIN_ATTEMPTS}")

        conn.commit()
        conn.close()

        return {
            "locked_out": result.get("locked_until") is not None,
            "attempts": new_count if not success else 0,
            "lockout_until": result.get("locked_until") if not success else None
        }

    except Exception as e:
        auth_logger.error(f"Error recording login attempt for {username}: {e}")
        return {"locked_out": False, "attempts": 0, "lockout_until": None}


def cleanup_expired_sessions():
    """Delete expired sessions from the database."""
    try:
        conn = get_conn()
        now = datetime.utcnow().isoformat(timespec="seconds")

        result = conn.execute(
            "DELETE FROM sessions WHERE expires_at < ?",
            (now,)
        )

        deleted_count = result.rowcount
        conn.commit()
        conn.close()

        if deleted_count > 0:
            auth_logger.info(f"Cleaned up {deleted_count} expired sessions")

        return deleted_count

    except Exception as e:
        auth_logger.error(f"Error cleaning up expired sessions: {e}")
        return 0


def cleanup_old_login_attempts():
    """Delete old login attempt records (older than 30 days)."""
    try:
        conn = get_conn()
        cutoff_date = (datetime.utcnow() - timedelta(days=30)).isoformat()

        result = conn.execute(
            "DELETE FROM login_attempts WHERE last_attempt_at < ?",
            (cutoff_date,)
        )

        deleted_count = result.rowcount
        conn.commit()
        conn.close()

        if deleted_count > 0:
            auth_logger.info(f"Cleaned up {deleted_count} old login attempt records")

        return deleted_count

    except Exception as e:
        auth_logger.error(f"Error cleaning up old login attempts: {e}")
        return 0
