"""Dashboard password hashing, sessions, login throttling and reset tokens (shared design with avalon-dashboard)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
from dataclasses import dataclass

ITERATIONS = 600_000
MAX_FAILURES = 5
LOCKOUT_S = 60


def hash_password(password: str, iterations: int = ITERATIONS) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt, digest = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters)).hex()
    except ValueError:
        return False
    return hmac.compare_digest(calc, digest)


@dataclass
class Session:
    expires: float
    csrf: str


class Sessions:
    def __init__(self, password_hash: str, ttl: float = 7 * 24 * 3600):
        self.password_hash = password_hash
        self.ttl = ttl
        self._sessions: dict[str, Session] = {}
        self._failures = 0
        self._locked_until = 0.0
        self._lock = threading.Lock()

    def locked(self, now: float) -> bool:
        return now < self._locked_until

    def login(self, password: str, now: float) -> str | None:
        with self._lock:
            if self.locked(now):
                return None
            if not verify_password(password, self.password_hash):
                self._failures += 1
                if self._failures >= MAX_FAILURES:
                    self._failures = 0
                    self._locked_until = now + LOCKOUT_S
                return None
            self._failures = 0
            token = secrets.token_hex(32)
            self._sessions[token] = Session(now + self.ttl, secrets.token_hex(32))
            return token

    def get(self, token: str | None, now: float) -> Session | None:
        if not token:
            return None
        with self._lock:
            sess = self._sessions.get(token)
            if sess and now >= sess.expires:
                del self._sessions[token]
                return None
            return sess

    def logout(self, token: str | None) -> None:
        with self._lock:
            self._sessions.pop(token or "", None)

    def set_password(self, new_hash: str, keep: str | None = None) -> None:
        """Install a new password hash and sign out every session except `keep`."""
        with self._lock:
            self.password_hash = new_hash
            self._sessions = {t: s for t, s in self._sessions.items() if t == keep}
            self._failures = 0
            self._locked_until = 0.0


MIN_PASSWORD_LEN = 8
RESET_TTL_S = 15 * 60
RESET_EMAIL_INTERVAL_S = 5 * 60


def password_problem(new: str, repeat: str) -> str | None:
    if new != repeat:
        return "The two new passwords don't match."
    if len(new) < MIN_PASSWORD_LEN:
        return f"Use at least {MIN_PASSWORD_LEN} characters."
    return None


class ResetTokens:
    """One-time password-reset tokens (kept in memory; only a hash is stored)."""

    def __init__(self):
        self._tokens: dict[str, float] = {}
        self._last_issued = -RESET_EMAIL_INTERVAL_S
        self._lock = threading.Lock()

    @staticmethod
    def _h(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def issue(self, now: float) -> str | None:
        """New token, or None if one was issued less than 5 minutes ago (limits email floods)."""
        with self._lock:
            if now - self._last_issued < RESET_EMAIL_INTERVAL_S:
                return None
            self._last_issued = now
            token = secrets.token_urlsafe(32)
            self._tokens = {self._h(token): now + RESET_TTL_S}  # a new link voids older ones
            return token

    def valid(self, token: str, now: float) -> bool:
        with self._lock:
            exp = self._tokens.get(self._h(token or ""))
            return exp is not None and now < exp

    def consume(self, token: str, now: float) -> bool:
        with self._lock:
            exp = self._tokens.pop(self._h(token or ""), None)
            return exp is not None and now < exp
