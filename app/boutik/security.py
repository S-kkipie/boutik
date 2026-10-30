"""PIN auth, sessions, lockout, rate limiting and HTTP security headers."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time
from collections import defaultdict, deque

from .db import DB, now

PIN_RE = re.compile(r"^\d{4,8}$")
SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}
MAX_FAILURES = 5
LOCKOUT_S = 300

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; manifest-src 'self'; worker-src 'self'; object-src 'none'; "
    "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
)
SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(self), microphone=(self), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


def hash_pin(pin: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.scrypt(pin.encode(), salt=salt, **SCRYPT)
    return f"scrypt${salt.hex()}${dk.hex()}"


def verify_pin(pin: str, stored: str) -> bool:
    try:
        _, salt_hex, dk_hex = stored.split("$")
    except ValueError:
        return False
    dk = hashlib.scrypt(pin.encode(), salt=bytes.fromhex(salt_hex), **SCRYPT)
    return hmac.compare_digest(dk.hex(), dk_hex)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Auth:
    """Single-merchant PIN auth. Session tokens are stored hashed."""

    def __init__(self, db: DB, ttl_s: int):
        self.db = db
        self.ttl_s = ttl_s
        self._failures: deque[float] = deque()
        self._locked_until = 0.0

    def has_pin(self) -> bool:
        return self.db.get_setting("pin_hash") is not None

    def set_pin(self, pin: str) -> None:
        if not PIN_RE.match(pin):
            raise ValueError("PIN must be 4 to 8 digits")
        self.db.set_setting("pin_hash", hash_pin(pin))

    def locked_for(self) -> int:
        return max(0, int(self._locked_until - time.time()))

    def check_pin(self, pin: str) -> bool:
        """Constant-time check with a global lockout (one shop, one PIN)."""
        if self.locked_for():
            return False
        stored = self.db.get_setting("pin_hash")
        ok = bool(stored) and PIN_RE.match(pin or "") is not None and verify_pin(pin, stored)
        if ok:
            self._failures.clear()
            return True
        t = time.time()
        self._failures.append(t)
        while self._failures and t - self._failures[0] > LOCKOUT_S:
            self._failures.popleft()
        if len(self._failures) >= MAX_FAILURES:
            self._locked_until = t + LOCKOUT_S
            self._failures.clear()
        return False

    def new_session(self) -> str:
        token = secrets.token_urlsafe(32)
        self.db.exec("DELETE FROM sessions WHERE expires_at < ?", (now(),))
        self.db.exec(
            "INSERT INTO sessions(token_hash, expires_at) VALUES(?,?)",
            (_token_hash(token), now() + self.ttl_s),
        )
        return token

    def valid_session(self, token: str | None) -> bool:
        if not token:
            return False
        row = self.db.one("SELECT expires_at FROM sessions WHERE token_hash=?", (_token_hash(token),))
        return bool(row) and row["expires_at"] > now()

    def end_session(self, token: str | None) -> None:
        if token:
            self.db.exec("DELETE FROM sessions WHERE token_hash=?", (_token_hash(token),))


class RateLimiter:
    """Sliding-window limiter, in memory (one process per shop)."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int, window_s: int) -> bool:
        t = time.time()
        q = self._hits[key]
        while q and t - q[0] > window_s:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(t)
        if len(self._hits) > 10_000:  # bound memory under abuse
            self._hits.clear()
        return True
