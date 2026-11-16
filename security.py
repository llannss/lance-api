"""Who is calling, and how often.

Shared FastAPI dependencies used by index.py and chat.py:
- get_current_user: reads the login token (cookie or Bearer header), then
  re-checks the account in the database on every request, so deleted,
  demoted or signed-out accounts lose access immediately.
- require_admin: allows the request only for the admin role.
- enforce_rate_limit: shared database counters that work on serverless.
"""

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import auth
from database import RateLimiter, UserRepository, get_user_repository

# The browser keeps the login token in this HttpOnly cookie, which page
# scripts cannot read. API clients such as Swagger can send
# "Authorization: Bearer <token>" instead.
SESSION_COOKIE = "gpu_session"

# Cookie-authenticated writes must prove they came from a page on this site,
# so another website cannot forge a write with the user's cookie. Either is
# accepted:
# - X-Requested-With: browsers only let a page add custom headers to
#   same-origin requests (or ones CORS allows). The website sends it.
# - Sec-Fetch-Site: same-origin: set by the browser itself and impossible for
#   page scripts to change. Covers Swagger UI at /docs after /auth/login.
CSRF_HEADER = "x-requested-with"
FETCH_SITE_HEADER = "sec-fetch-site"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _is_same_site_request(request: Request) -> bool:
    return bool(request.headers.get(CSRF_HEADER)) or (
        request.headers.get(FETCH_SITE_HEADER) == "same-origin"
    )

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Paste the access_token returned by POST /auth/login.",
)


def _not_logged_in() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="Log in to continue.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    users: UserRepository = Depends(get_user_repository),
) -> dict:
    """Return the logged-in account, or answer 401."""
    from_cookie = False
    if credentials is not None:
        token = credentials.credentials
    else:
        token = request.cookies.get(SESSION_COOKIE)
        from_cookie = True
    if not token:
        raise _not_logged_in()

    try:
        claims = auth.read_token(token)
    except auth.InvalidTokenError:
        raise _not_logged_in()

    if from_cookie and request.method not in SAFE_METHODS and not _is_same_site_request(request):
        raise HTTPException(
            status_code=403,
            detail="Changes signed in with the session cookie must come from this site.",
        )

    # The token only says who the caller was when they logged in. The
    # database says who they are now.
    account = users.get(claims["id"])
    if (
        account is None
        or int(account.get("token_version", 0)) != claims["ver"]
        or not account.get("email_verified", False)
    ):
        raise _not_logged_in()
    return account


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Allow the request only for accounts with the admin role."""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access is required.")
    return user


def client_ip(request: Request) -> str:
    """The caller's IP address. Vercel overwrites X-Forwarded-For and X-Real-IP,
    so clients cannot fake them there."""
    for header in ("x-real-ip", "x-forwarded-for"):
        value = request.headers.get(header, "")
        if value:
            return value.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(
    limiter: RateLimiter, key: str, window_seconds: int, limit: int, message: str
) -> None:
    """Count one hit for key and answer 429 when it is over the limit."""
    if not limiter.hit(key, window_seconds, limit):
        raise HTTPException(
            status_code=429,
            detail=message,
            headers={"Retry-After": str(window_seconds)},
        )
