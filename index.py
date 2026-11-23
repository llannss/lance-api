"""GPU Finder API, version 2.

The GPU catalog and the user accounts are stored in a Supabase (PostgreSQL)
database. Users sign up and log in to browse the catalog. Only accounts with
the admin role can add, update or delete GPUs.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, File, HTTPException, Path, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import activity
import auth
import chat
import favorites
import market
import images
import mailer
from config import get_settings
from database import (
    DatabaseUnavailableError,
    DuplicateEmailError,
    DuplicateGPUError,
    AuditRepository,
    GPURepository,
    ImageStore,
    InvalidGPUError,
    RateLimiter,
    TokenRepository,
    UserRepository,
    get_audit_repository,
    get_image_store,
    get_rate_limiter,
    get_repository,
    get_token_repository,
    get_user_repository,
)
from models import (
    GPU,
    MAX_ID,
    Credentials,
    EmailOnly,
    GPUCreate,
    GPUList,
    GPUSearchResults,
    LoginResult,
    Message,
    ResetPassword,
    User,
    VerifyEmail,
)
from security import (
    SESSION_COOKIE,
    client_ip,
    enforce_rate_limit,
    get_current_user,
    require_admin,
    require_reader,
)

logger = logging.getLogger("gpu_api")

SERVICE_NAME = "GPU Finder API"
VERSION = "2.1.0"

# ---------- sign-in limits ----------
MAX_FAILED_LOGINS = 5                   # wrong passwords before the account locks
LOCKOUT = timedelta(minutes=15)
VERIFY_LINK_LIFETIME = timedelta(hours=24)
RESET_LINK_LIFETIME = timedelta(minutes=30)
# (window seconds, max hits) per IP address or email
LOGIN_PER_IP = (15 * 60, 20)
REGISTER_PER_IP = (60 * 60, 5)
EMAIL_LINKS_PER_IP = (60 * 60, 10)
EMAIL_LINKS_PER_ADDRESS = (60 * 60, 3)

app = FastAPI(
    title=SERVICE_NAME,
    description=(
        "A REST API for browsing and managing a GPU catalog stored in a "
        "Supabase database. Sign up and log in to browse. Creating, updating, "
        "and deleting GPUs requires an admin account. To use a protected "
        "endpoint here, call POST /auth/login, copy the access_token, and "
        "paste it into Authorize."
    ),
    version=VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(favorites.router)
app.include_router(market.router)
app.include_router(activity.recent_router)
app.include_router(activity.comparisons_router)
app.include_router(activity.audit_router)

GPU_NOT_FOUND = "GPU not found."
LINK_INVALID = "This link is invalid or has expired."
# Same answer whether or not the email has an account.
EMAIL_SENT_IF_EXISTS = "If that email belongs to an account, we've sent it a link."
# The same message for a wrong email and a wrong password, so nobody can
# use the login form to find out which emails have accounts.
LOGIN_FAILED = "Invalid email or password."
# Used to spend the same time on a login for an email that has no account.
DUMMY_HASH = auth.hash_password("not-a-real-password")


# ---------- ERROR RESPONSES ----------
# Each handler returns a short, general message. Database details stay in the server log.

@app.exception_handler(DatabaseUnavailableError)
def database_unavailable(request: Request, error: DatabaseUnavailableError):
    return JSONResponse(
        status_code=503,
        content={"detail": "The database is currently unavailable. Please try again later."},
    )


@app.exception_handler(DuplicateGPUError)
def duplicate_gpu(request: Request, error: DuplicateGPUError):
    return JSONResponse(
        status_code=409,
        content={"detail": "A GPU with this brand, manufacturer, and model already exists."},
    )


@app.exception_handler(DuplicateEmailError)
def duplicate_email(request: Request, error: DuplicateEmailError):
    return JSONResponse(
        status_code=409,
        content={"detail": "An account with this email already exists."},
    )


@app.exception_handler(InvalidGPUError)
def invalid_values(request: Request, error: InvalidGPUError):
    return JSONResponse(
        status_code=422,
        content={"detail": "The database rejected the submitted values."},
    )


@app.exception_handler(auth.AuthNotConfiguredError)
def auth_not_configured(request: Request, error: auth.AuthNotConfiguredError):
    return JSONResponse(
        status_code=503,
        content={"detail": "Login is not configured on the server."},
    )


@app.exception_handler(mailer.EmailNotConfiguredError)
def email_not_configured(request: Request, error: mailer.EmailNotConfiguredError):
    return JSONResponse(
        status_code=503,
        content={"detail": "Email is not configured on the server."},
    )


GpuId = Path(ge=1, le=MAX_ID, description="The ID of the GPU.")


# ---------- HOME ----------

@app.get("/", tags=["General"])
def home():
    return {
        "message": "Welcome to the GPU Finder API!",
        "version": VERSION,
        "endpoints": [
            "GET /health",
            "POST /auth/register",
            "POST /auth/verify",
            "POST /auth/resend-verification",
            "POST /auth/login",
            "POST /auth/logout",
            "POST /auth/logout-all",
            "POST /auth/forgot-password",
            "POST /auth/reset-password",
            "GET /auth/me",
            "POST /chat",
            "GET /me/favorites",
            "PUT /me/favorites/{gpu_id}",
            "DELETE /me/favorites/{gpu_id}",
            "GET /me/recent",
            "POST /me/recent/{gpu_id}",
            "DELETE /me/recent",
            "GET /me/comparisons",
            "POST /me/comparisons",
            "DELETE /me/comparisons/{comparison_id}",
            "GET /admin/audit",
            "GET /gpus",
            "GET /gpus/search?q=keyword",
            "GET /gpus/{gpu_id}",
            "POST /gpus",
            "PUT /gpus/{gpu_id}",
            "DELETE /gpus/{gpu_id}",
            "POST /gpus/{gpu_id}/image",
            "DELETE /gpus/{gpu_id}/image",
        ],
    }


# ---------- HEALTH CHECK ----------

@app.get("/health", tags=["General"])
def health_check(repository: GPURepository = Depends(get_repository)):
    body = {
        "status": "healthy",
        "service": SERVICE_NAME,
        "version": VERSION,
        "database": "connected",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        repository.ping()
    except DatabaseUnavailableError:
        body["status"] = "unhealthy"
        body["database"] = "unavailable"
        return JSONResponse(status_code=503, content=body)
    return body


# ---------- helpers for the account routes ----------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _send_link(tokens: TokenRepository, user: dict, purpose: str) -> None:
    """Create a one-time link for the account and email it.

    Older unused links of the same kind stop working, so only the newest
    email in the inbox is valid.
    """
    lifetime = VERIFY_LINK_LIFETIME if purpose == "verify" else RESET_LINK_LIFETIME
    secret, secret_hash = auth.new_link_secret()
    tokens.revoke_all(user["id"], purpose)
    tokens.create(user["id"], purpose, secret_hash, _now() + lifetime)
    if purpose == "verify":
        mailer.send_verification_email(user["email"], secret)
    else:
        mailer.send_password_reset_email(user["email"], secret)


def _limit_email_links(request: Request, limiter: RateLimiter, email: str) -> None:
    message = "Too many email requests. Try again in an hour."
    enforce_rate_limit(limiter, f"email-ip:{client_ip(request)}", *EMAIL_LINKS_PER_IP, message)
    enforce_rate_limit(limiter, f"email-to:{email}", *EMAIL_LINKS_PER_ADDRESS, message)


def _set_session_cookie(response: Response, token: str, max_age: int) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        httponly=True,       # page scripts cannot read it
        secure=True,         # HTTPS only (browsers also allow it on localhost)
        samesite="strict",   # never sent on requests started by other sites
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="strict")


# ---------- SIGN UP ----------

@app.post("/auth/register", response_model=User, status_code=201, tags=["Accounts"])
def register(
    credentials: Credentials,
    request: Request,
    users: UserRepository = Depends(get_user_repository),
    tokens: TokenRepository = Depends(get_token_repository),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    """Create an account and email a confirmation link. The account can log
    in only after the link is opened."""
    enforce_rate_limit(
        limiter, f"register-ip:{client_ip(request)}", *REGISTER_PER_IP,
        "Too many sign-ups from this network. Try again in an hour.",
    )
    if not mailer.is_configured():
        raise mailer.EmailNotConfiguredError()
    password_hash = auth.hash_password(credentials.password)
    user = users.create(credentials.email, password_hash)
    try:
        _send_link(tokens, user, "verify")
    except Exception as error:
        # The account exists; the user can ask for a new link later.
        logger.error("Verification email failed: %s", type(error).__name__)
    return user


# ---------- VERIFY EMAIL ----------

@app.post("/auth/verify", response_model=Message, tags=["Accounts"])
def verify_email(
    body: VerifyEmail,
    users: UserRepository = Depends(get_user_repository),
    tokens: TokenRepository = Depends(get_token_repository),
):
    user_id = tokens.consume(auth.hash_link_secret(body.token), "verify")
    if user_id is None:
        raise HTTPException(status_code=400, detail=LINK_INVALID)
    users.update(user_id, {"email_verified": True})
    return {"detail": "Email confirmed. You can sign in now."}


@app.post("/auth/resend-verification", response_model=Message, status_code=202, tags=["Accounts"])
def resend_verification(
    body: EmailOnly,
    request: Request,
    users: UserRepository = Depends(get_user_repository),
    tokens: TokenRepository = Depends(get_token_repository),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    _limit_email_links(request, limiter, body.email)
    if not mailer.is_configured():
        raise mailer.EmailNotConfiguredError()
    user = users.get_for_login(body.email)
    if user and not user.get("email_verified"):
        _send_link(tokens, user, "verify")
    return {"detail": EMAIL_SENT_IF_EXISTS}


# ---------- LOG IN ----------

@app.post("/auth/login", response_model=LoginResult, tags=["Accounts"])
def login(
    credentials: Credentials,
    request: Request,
    response: Response,
    users: UserRepository = Depends(get_user_repository),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    """Check the password and start a session.

    The browser receives an HttpOnly cookie. The token is also returned in
    the body for API clients such as Swagger.
    """
    enforce_rate_limit(
        limiter, f"login-ip:{client_ip(request)}", *LOGIN_PER_IP,
        "Too many sign-in attempts. Try again in 15 minutes.",
    )
    user = users.get_for_login(credentials.email)

    locked_until = user.get("locked_until") if user else None
    if locked_until and datetime.fromisoformat(locked_until) > _now():
        raise HTTPException(
            status_code=429,
            detail="Too many wrong passwords. This account is locked for 15 minutes.",
        )

    stored_hash = user["password_hash"] if user else DUMMY_HASH
    password_ok = auth.verify_password(credentials.password, stored_hash)
    if user is None or not password_ok:
        if user is not None:
            failed = int(user.get("failed_logins") or 0) + 1
            if failed >= MAX_FAILED_LOGINS:
                users.update(user["id"], {
                    "failed_logins": 0,
                    "locked_until": (_now() + LOCKOUT).isoformat(),
                })
            else:
                users.update(user["id"], {"failed_logins": failed})
        raise HTTPException(status_code=401, detail=LOGIN_FAILED)

    if user.get("failed_logins") or user.get("locked_until"):
        users.update(user["id"], {"failed_logins": 0, "locked_until": None})

    if not user.get("email_verified"):
        raise HTTPException(
            status_code=403,
            detail="Confirm your email first. Check your inbox for the link.",
        )

    token, expires_in = auth.create_token(user)
    _set_session_cookie(response, token, expires_in)
    return {"access_token": token, "expires_in": expires_in, "user": user}


# ---------- LOG OUT ----------

@app.post("/auth/logout", status_code=204, tags=["Accounts"])
def logout():
    """End the session in this browser."""
    response = Response(status_code=204)
    _clear_session_cookie(response)
    return response


@app.post("/auth/logout-all", status_code=204, tags=["Accounts"])
def logout_everywhere(
    user: dict = Depends(get_current_user),
    users: UserRepository = Depends(get_user_repository),
):
    """End every session of this account on every device."""
    users.update(user["id"], {"token_version": int(user.get("token_version", 0)) + 1})
    response = Response(status_code=204)
    _clear_session_cookie(response)
    return response


# ---------- PASSWORD RESET ----------

@app.post("/auth/forgot-password", response_model=Message, status_code=202, tags=["Accounts"])
def forgot_password(
    body: EmailOnly,
    request: Request,
    users: UserRepository = Depends(get_user_repository),
    tokens: TokenRepository = Depends(get_token_repository),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    """Email a password reset link. Answers the same way for unknown emails."""
    _limit_email_links(request, limiter, body.email)
    if not mailer.is_configured():
        raise mailer.EmailNotConfiguredError()
    user = users.get_for_login(body.email)
    if user:
        _send_link(tokens, user, "reset")
    return {"detail": EMAIL_SENT_IF_EXISTS}


@app.post("/auth/reset-password", response_model=Message, tags=["Accounts"])
def reset_password(
    body: ResetPassword,
    users: UserRepository = Depends(get_user_repository),
    tokens: TokenRepository = Depends(get_token_repository),
):
    """Set a new password from an emailed link. Signs the account out everywhere."""
    user_id = tokens.consume(auth.hash_link_secret(body.token), "reset")
    if user_id is None:
        raise HTTPException(status_code=400, detail=LINK_INVALID)
    account = users.get(user_id)
    if account is None:
        raise HTTPException(status_code=400, detail=LINK_INVALID)
    users.update(user_id, {
        "password_hash": auth.hash_password(body.password),
        "token_version": int(account.get("token_version", 0)) + 1,
        "failed_logins": 0,
        "locked_until": None,
        # Opening the emailed link proves the address works.
        "email_verified": True,
    })
    tokens.revoke_all(user_id, "reset")
    return {"detail": "Password changed. Sign in with your new password."}


# ---------- CURRENT ACCOUNT ----------

@app.get("/auth/me", response_model=User, tags=["Accounts"])
def current_account(user: dict = Depends(get_current_user)):
    return user


# ---------- GET ALL GPUS ----------

@app.get(
    "/gpus",
    response_model=GPUList,
    dependencies=[Depends(require_reader)],
    tags=["GPUs"],
)
def get_gpus(response: Response, repository: GPURepository = Depends(get_repository)):
    rows = repository.list_all()
    # The catalog is the same for every reader, so a browser may keep it for a
    # minute when it asks to (the Marketplace does; the admin page and Finder
    # send no-store and always get a fresh copy). "private": never cached by
    # Vercel's shared edge, which would skip the sign-in check.
    response.headers["Cache-Control"] = "private, max-age=60"
    return {"count": len(rows), "gpus": rows}


# ---------- SEARCH GPUS ----------

@app.get(
    "/gpus/search",
    response_model=GPUSearchResults,
    dependencies=[Depends(require_reader)],
    tags=["GPUs"],
)
def search_gpus(
    q: str = Query(..., min_length=1, max_length=100, description="Keyword to search for."),
    repository: GPURepository = Depends(get_repository),
):
    q = q.lower().strip()
    if not q:
        raise HTTPException(status_code=422, detail="The search keyword cannot be blank.")
    results = repository.search(q)
    return {"query": q, "count": len(results), "results": results}


# ---------- GET ONE GPU ----------

@app.get(
    "/gpus/{gpu_id}",
    response_model=GPU,
    dependencies=[Depends(require_reader)],
    tags=["GPUs"],
)
def get_gpu(gpu_id: int = GpuId, repository: GPURepository = Depends(get_repository)):
    gpu = repository.get(gpu_id)
    if gpu is None:
        raise HTTPException(status_code=404, detail=GPU_NOT_FOUND)
    return gpu


# ---------- CREATE A GPU ----------

@app.post(
    "/gpus",
    response_model=GPU,
    status_code=201,
    tags=["GPUs"],
)
def create_gpu(
    gpu: GPUCreate,
    response: Response,
    repository: GPURepository = Depends(get_repository),
    admin: dict = Depends(require_admin),
    audit: AuditRepository = Depends(get_audit_repository),
):
    created = repository.create(gpu.model_dump(mode="json"))
    activity.record(audit, admin, "gpu.create", created)
    response.headers["Location"] = f"/gpus/{created['id']}"
    return created


# ---------- UPDATE A GPU ----------

@app.put(
    "/gpus/{gpu_id}",
    response_model=GPU,
    tags=["GPUs"],
)
def update_gpu(
    gpu: GPUCreate,
    gpu_id: int = GpuId,
    repository: GPURepository = Depends(get_repository),
    admin: dict = Depends(require_admin),
    audit: AuditRepository = Depends(get_audit_repository),
):
    before = repository.get(gpu_id)
    if before is None:
        raise HTTPException(status_code=404, detail=GPU_NOT_FOUND)
    updated = repository.update(gpu_id, gpu.model_dump(mode="json"))
    if updated is None:
        raise HTTPException(status_code=404, detail=GPU_NOT_FOUND)
    changes = activity.diff(before, updated)
    if changes:
        activity.record(audit, admin, "gpu.update", updated, changes)
    return updated


# ---------- DELETE A GPU ----------

@app.delete(
    "/gpus/{gpu_id}",
    status_code=204,
    tags=["GPUs"],
)
def delete_gpu(
    gpu_id: int = GpuId,
    repository: GPURepository = Depends(get_repository),
    store: ImageStore = Depends(get_image_store),
    admin: dict = Depends(require_admin),
    audit: AuditRepository = Depends(get_audit_repository),
):
    deleted = repository.delete(gpu_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail=GPU_NOT_FOUND)
    activity.record(audit, admin, "gpu.delete", deleted)
    store.remove_url(deleted.get("image_url"))
    return Response(status_code=204)


# ---------- GPU PICTURE ----------

@app.post(
    "/gpus/{gpu_id}/image",
    response_model=GPU,
    tags=["GPUs"],
    responses={413: {"description": "File over 4 MB"}, 422: {"description": "Not a PNG, JPEG or WebP picture"}},
)
def upload_gpu_image(
    gpu_id: int = GpuId,
    file: UploadFile = File(description="A PNG, JPEG or WebP picture, up to 4 MB."),
    repository: GPURepository = Depends(get_repository),
    store: ImageStore = Depends(get_image_store),
    admin: dict = Depends(require_admin),
    audit: AuditRepository = Depends(get_audit_repository),
):
    """Set or replace a GPU's picture. The file is checked, resized to at most
    1000 px and converted to WebP before it is stored in Supabase Storage."""
    gpu = repository.get(gpu_id)
    if gpu is None:
        raise HTTPException(status_code=404, detail=GPU_NOT_FOUND)

    data = file.file.read(images.MAX_UPLOAD_BYTES + 1)
    try:
        webp = images.to_webp(data)
    except images.ImageTooLargeError:
        raise HTTPException(status_code=413, detail="The picture must be 4 MB or smaller.")
    except images.InvalidImageError:
        raise HTTPException(status_code=422, detail="Upload a PNG, JPEG or WebP picture.")

    # The server picks the name, so uploads can't overwrite other files.
    url = store.upload(f"gpu-{gpu_id}-{secrets.token_hex(8)}.webp", webp)
    updated = repository.set_image_url(gpu_id, url)
    if updated is None:              # the GPU was deleted meanwhile
        store.remove_url(url)
        raise HTTPException(status_code=404, detail=GPU_NOT_FOUND)
    store.remove_url(gpu.get("image_url"))
    activity.record(audit, admin, "image.upload", updated)
    return updated


@app.delete(
    "/gpus/{gpu_id}/image",
    response_model=GPU,
    tags=["GPUs"],
)
def delete_gpu_image(
    gpu_id: int = GpuId,
    repository: GPURepository = Depends(get_repository),
    store: ImageStore = Depends(get_image_store),
    admin: dict = Depends(require_admin),
    audit: AuditRepository = Depends(get_audit_repository),
):
    """Remove a GPU's picture. The website then shows its built-in placeholder."""
    gpu = repository.get(gpu_id)
    if gpu is None:
        raise HTTPException(status_code=404, detail=GPU_NOT_FOUND)
    updated = repository.set_image_url(gpu_id, None)
    if updated is None:
        raise HTTPException(status_code=404, detail=GPU_NOT_FOUND)
    store.remove_url(gpu.get("image_url"))
    if gpu.get("image_url"):
        activity.record(audit, admin, "image.remove", updated)
    return updated
