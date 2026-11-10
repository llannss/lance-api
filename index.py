"""GPU Finder API, version 2.

The GPU catalog and the user accounts are stored in a Supabase (PostgreSQL)
database. Users sign up and log in to browse the catalog. Only accounts with
the admin role can add, update or delete GPUs.
"""

from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import auth
from config import get_settings
from database import (
    DatabaseUnavailableError,
    DuplicateEmailError,
    DuplicateGPUError,
    GPURepository,
    InvalidGPUError,
    UserRepository,
    get_repository,
    get_user_repository,
)
from models import (
    GPU,
    MAX_ID,
    Credentials,
    GPUCreate,
    GPUList,
    GPUSearchResults,
    LoginResult,
    User,
)

SERVICE_NAME = "GPU Finder API"
VERSION = "2.0.0"

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

GPU_NOT_FOUND = "GPU not found."
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


# ---------- WHO IS CALLING ----------

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Paste the access_token returned by POST /auth/login.",
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """Return the logged-in user, or answer 401 if the token is missing or invalid."""
    try:
        if credentials is None:
            raise auth.InvalidTokenError()
        return auth.read_token(credentials.credentials)
    except auth.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Log in to continue.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Allow the request only for accounts with the admin role."""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access is required.")
    return user


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
            "POST /auth/login",
            "GET /auth/me",
            "GET /gpus",
            "GET /gpus/search?q=keyword",
            "GET /gpus/{gpu_id}",
            "POST /gpus",
            "PUT /gpus/{gpu_id}",
            "DELETE /gpus/{gpu_id}",
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


# ---------- SIGN UP ----------

@app.post("/auth/register", response_model=User, status_code=201, tags=["Accounts"])
def register(
    credentials: Credentials,
    users: UserRepository = Depends(get_user_repository),
):
    password_hash = auth.hash_password(credentials.password)
    return users.create(credentials.email, password_hash)


# ---------- LOG IN ----------

@app.post("/auth/login", response_model=LoginResult, tags=["Accounts"])
def login(
    credentials: Credentials,
    users: UserRepository = Depends(get_user_repository),
):
    user = users.get_for_login(credentials.email)
    stored_hash = user["password_hash"] if user else DUMMY_HASH
    password_ok = auth.verify_password(credentials.password, stored_hash)
    if user is None or not password_ok:
        raise HTTPException(status_code=401, detail=LOGIN_FAILED)
    token, expires_in = auth.create_token(user)
    return {"access_token": token, "expires_in": expires_in, "user": user}


# ---------- CURRENT ACCOUNT ----------

@app.get("/auth/me", response_model=User, tags=["Accounts"])
def current_account(
    user: dict = Depends(get_current_user),
    users: UserRepository = Depends(get_user_repository),
):
    account = users.get(user["id"])
    if account is None:
        raise HTTPException(
            status_code=401,
            detail="Log in to continue.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return account


# ---------- GET ALL GPUS ----------

@app.get(
    "/gpus",
    response_model=GPUList,
    dependencies=[Depends(get_current_user)],
    tags=["GPUs"],
)
def get_gpus(repository: GPURepository = Depends(get_repository)):
    rows = repository.list_all()
    return {"count": len(rows), "gpus": rows}


# ---------- SEARCH GPUS ----------

@app.get(
    "/gpus/search",
    response_model=GPUSearchResults,
    dependencies=[Depends(get_current_user)],
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
    dependencies=[Depends(get_current_user)],
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
    dependencies=[Depends(require_admin)],
    tags=["GPUs"],
)
def create_gpu(
    gpu: GPUCreate,
    response: Response,
    repository: GPURepository = Depends(get_repository),
):
    created = repository.create(gpu.model_dump(mode="json"))
    response.headers["Location"] = f"/gpus/{created['id']}"
    return created


# ---------- UPDATE A GPU ----------

@app.put(
    "/gpus/{gpu_id}",
    response_model=GPU,
    dependencies=[Depends(require_admin)],
    tags=["GPUs"],
)
def update_gpu(
    gpu: GPUCreate,
    gpu_id: int = GpuId,
    repository: GPURepository = Depends(get_repository),
):
    updated = repository.update(gpu_id, gpu.model_dump(mode="json"))
    if updated is None:
        raise HTTPException(status_code=404, detail=GPU_NOT_FOUND)
    return updated


# ---------- DELETE A GPU ----------

@app.delete(
    "/gpus/{gpu_id}",
    status_code=204,
    dependencies=[Depends(require_admin)],
    tags=["GPUs"],
)
def delete_gpu(gpu_id: int = GpuId, repository: GPURepository = Depends(get_repository)):
    if not repository.delete(gpu_id):
        raise HTTPException(status_code=404, detail=GPU_NOT_FOUND)
    return Response(status_code=204)
