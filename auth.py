"""Passwords and login tokens.

Passwords are never stored. Only a salted PBKDF2 hash is saved in the users
table. After a successful login the API gives the client a signed token that
it sends back with every request.
"""

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from config import get_settings

# Password hashing settings.
PBKDF2_ITERATIONS = 600_000
SALT_BYTES = 16

# Login token settings.
TOKEN_HOURS = 8
TOKEN_ALGORITHM = "HS256"
MIN_SECRET_LENGTH = 32


class AuthNotConfiguredError(Exception):
    """AUTH_SECRET is missing or too short."""


class InvalidTokenError(Exception):
    """The token is missing, expired, changed, or not one of ours."""


# ---------- passwords ----------

def hash_password(password: str) -> str:
    """Return a salted hash in the form pbkdf2_sha256$iterations$salt$hash."""
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return "$".join([
        "pbkdf2_sha256",
        str(PBKDF2_ITERATIONS),
        base64.b64encode(salt).decode(),
        base64.b64encode(digest).decode(),
    ])


def verify_password(password: str, stored_hash: str) -> bool:
    """Check a password against a stored hash without leaking timing."""
    try:
        scheme, iterations, salt, digest = stored_hash.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        expected = base64.b64decode(digest)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), base64.b64decode(salt), int(iterations)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# ---------- tokens ----------

def _secret() -> str:
    secret = get_settings().auth_secret
    if len(secret) < MIN_SECRET_LENGTH:
        raise AuthNotConfiguredError()
    return secret


def create_token(user: dict) -> tuple[str, int]:
    """Return a signed login token for the user and its lifetime in seconds."""
    now = datetime.now(timezone.utc)
    lifetime = timedelta(hours=TOKEN_HOURS)
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
        "iat": now,
        "exp": now + lifetime,
    }
    token = jwt.encode(payload, _secret(), algorithm=TOKEN_ALGORITHM)
    return token, int(lifetime.total_seconds())


def read_token(token: str) -> dict:
    """Return the user stored in a token, or raise InvalidTokenError."""
    secret = _secret()
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[TOKEN_ALGORITHM],
            options={"require": ["sub", "email", "role", "exp"]},
        )
        return {
            "id": int(payload["sub"]),
            "email": str(payload["email"]),
            "role": str(payload["role"]),
        }
    except (jwt.PyJWTError, ValueError, TypeError) as error:
        raise InvalidTokenError() from error
