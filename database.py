"""Database access for the GPU catalog and the user accounts.

All Supabase queries live in GPURepository and UserRepository, so the
endpoint functions in index.py never talk to the database directly.
"""

import logging
from datetime import datetime, timezone
from functools import lru_cache

from supabase import Client, ClientOptions, PostgrestAPIError, create_client

from config import get_settings

logger = logging.getLogger("gpu_api.database")

# The columns the API returns. search_text is left out on purpose.
COLUMNS = (
    "id,brand,manufacturer,model,series,architecture,vram,memory_type,"
    "cuda_cores,core_count,core_type,memory_bus,memory_bandwidth_gbps,power,"
    "base_clock,boost_clock,recommended_psu,process_node_nm,pcie_interface,"
    "launch_price_usd,release_date,description,image_url"
)

# Supabase Storage bucket for GPU pictures (created by supabase/storage.sql).
IMAGE_BUCKET = "gpu-images"

# The account columns the API returns. password_hash is left out on purpose.
USER_COLUMNS = "id,email,role,created_at,email_verified,token_version,failed_logins,locked_until"

# Rows requested per query. Supabase may return fewer, so lists are read in batches.
BATCH_SIZE = 1000

# Seconds to wait for Supabase before giving up.
TIMEOUT_SECONDS = 10

# PostgreSQL error codes.
UNIQUE_VIOLATION = "23505"
INVALID_VALUE_CODES = {"23502", "23514", "22001", "22003", "22007", "22008", "22P02"}


class DatabaseUnavailableError(Exception):
    """The database could not be reached or a query failed."""


class DuplicateGPUError(Exception):
    """A GPU with the same brand, manufacturer and model already exists."""


class DuplicateEmailError(Exception):
    """An account with the same email already exists."""


class InvalidGPUError(Exception):
    """The database rejected the values because they break a table rule."""


class Repository:
    """Shared query helpers for one table."""

    duplicate_error: type[Exception] = DuplicateGPUError

    def __init__(self, client: Client):
        self.client = client

    def _run(self, query):
        """Run one query and turn any failure into an application error."""
        try:
            return query.execute()
        except PostgrestAPIError as error:
            if error.code == UNIQUE_VIOLATION:
                raise self.duplicate_error() from error
            if error.code in INVALID_VALUE_CODES:
                raise InvalidGPUError() from error
            # The details go to the server log only, never to the client.
            logger.error("Database query failed (code %s): %s", error.code, error.message)
            raise DatabaseUnavailableError() from error
        except Exception as error:
            logger.error("Database connection failed: %s", type(error).__name__)
            raise DatabaseUnavailableError() from error

    def _fetch_all(self, build_query) -> list[dict]:
        """Read every matching row, one batch at a time, in ID order."""
        rows: list[dict] = []
        while True:
            start = len(rows)
            response = self._run(
                build_query().order("id").range(start, start + BATCH_SIZE - 1)
            )
            batch = response.data or []
            rows.extend(batch)
            if not batch:
                break
            if response.count is not None and len(rows) >= response.count:
                break
        return rows


class GPURepository(Repository):
    """Reads and writes rows of the public.gpus table."""

    duplicate_error = DuplicateGPUError

    # ---------- read ----------

    def ping(self) -> None:
        """Query one ID to confirm the database answers."""
        self._run(self.client.table("gpus").select("id").limit(1))

    def list_all(self) -> list[dict]:
        return self._fetch_all(
            lambda: self.client.table("gpus").select(COLUMNS, count="exact")
        )

    def get(self, gpu_id: int) -> dict | None:
        response = self._run(
            self.client.table("gpus").select(COLUMNS).eq("id", gpu_id).limit(1)
        )
        return response.data[0] if response.data else None

    def search(self, keyword: str) -> list[dict]:
        """Case-insensitive keyword match against the search_text column."""
        # Make %, _ and \ match themselves instead of acting as wildcards.
        escaped = (
            keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        pattern = f"%{escaped}%"
        return self._fetch_all(
            lambda: self.client.table("gpus")
            .select(COLUMNS, count="exact")
            .ilike("search_text", pattern)
        )

    # ---------- write ----------

    def create(self, data: dict) -> dict:
        response = self._run(self.client.table("gpus").insert(data))
        if not response.data:
            raise DatabaseUnavailableError()
        return response.data[0]

    def update(self, gpu_id: int, data: dict) -> dict | None:
        response = self._run(
            self.client.table("gpus").update(data).eq("id", gpu_id)
        )
        return response.data[0] if response.data else None

    def delete(self, gpu_id: int) -> dict | None:
        """Delete a GPU and return the deleted row, or None if it did not exist."""
        response = self._run(self.client.table("gpus").delete().eq("id", gpu_id))
        return response.data[0] if response.data else None

    def set_image_url(self, gpu_id: int, image_url: str | None) -> dict | None:
        """Point a GPU at a picture (or none). Returns the updated GPU."""
        response = self._run(
            self.client.table("gpus").update({"image_url": image_url}).eq("id", gpu_id)
        )
        return response.data[0] if response.data else None


class ImageStore:
    """GPU pictures in the public Supabase Storage bucket.

    Files are named by the API (gpu-<id>-<random>.webp), so an upload can never
    overwrite another picture, and the public URL changes whenever the picture
    does, which keeps browser caches correct.
    """

    def __init__(self, client: Client):
        self.bucket = client.storage.from_(IMAGE_BUCKET)

    def upload(self, path: str, data: bytes) -> str:
        """Store a WebP file and return its public URL."""
        try:
            self.bucket.upload(path, data, {
                "content-type": "image/webp",
                "cache-control": "31536000",   # names never change, so cache for a year
                "upsert": "false",
            })
        except Exception as error:
            logger.error("Picture upload failed: %s", type(error).__name__)
            raise DatabaseUnavailableError() from error
        return self.bucket.get_public_url(path)

    def remove_url(self, url: str | None) -> None:
        """Delete the file behind one of our public URLs. Never raises:
        a leftover file is harmless, a failed GPU update is not."""
        path = self.path_from_url(url)
        if not path:
            return
        try:
            self.bucket.remove([path])
        except Exception as error:
            logger.warning("Could not delete old picture: %s", type(error).__name__)

    @staticmethod
    def path_from_url(url: str | None) -> str | None:
        """'.../storage/v1/object/public/gpu-images/x.webp' -> 'x.webp'.
        Returns None for anything that is not a file in our bucket."""
        marker = f"/storage/v1/object/public/{IMAGE_BUCKET}/"
        if not url or marker not in url:
            return None
        path = url.split(marker, 1)[1].split("?", 1)[0]
        return path if path and "/" not in path and ".." not in path else None


class UserRepository(Repository):
    """Reads and adds rows of the public.users table."""

    duplicate_error = DuplicateEmailError

    def get(self, user_id: int) -> dict | None:
        response = self._run(
            self.client.table("users").select(USER_COLUMNS).eq("id", user_id).limit(1)
        )
        return response.data[0] if response.data else None

    def get_for_login(self, email: str) -> dict | None:
        """Find an account by email, including its password hash."""
        response = self._run(
            self.client.table("users")
            .select(USER_COLUMNS + ",password_hash")
            .eq("email", email)
            .limit(1)
        )
        return response.data[0] if response.data else None

    def create(self, email: str, password_hash: str) -> dict:
        """Add an account. New accounts always get the role 'user'."""
        response = self._run(
            self.client.table("users").insert(
                {"email": email, "password_hash": password_hash}
            )
        )
        if not response.data:
            raise DatabaseUnavailableError()
        return response.data[0]

    def update(self, user_id: int, changes: dict) -> None:
        """Change account columns (only those users.sql/auth_upgrade.sql allow)."""
        self._run(self.client.table("users").update(changes).eq("id", user_id))


class TokenRepository(Repository):
    """One-time email links (verify email, reset password) in public.auth_tokens.

    Only a hash of each link's secret is stored, so a database leak does not
    reveal working links.
    """

    def create(self, user_id: int, purpose: str, token_hash: str, expires_at: datetime) -> None:
        self._run(self.client.table("auth_tokens").insert({
            "user_id": user_id,
            "purpose": purpose,
            "token_hash": token_hash,
            "expires_at": expires_at.isoformat(),
        }))

    def consume(self, token_hash: str, purpose: str) -> int | None:
        """Mark a valid, unused, unexpired link as used and return its user ID.

        Returns None for an unknown, used, expired or wrong-purpose link.
        """
        response = self._run(
            self.client.table("auth_tokens")
            .select("id,user_id,expires_at")
            .eq("token_hash", token_hash)
            .eq("purpose", purpose)
            .is_("used_at", "null")
            .limit(1)
        )
        if not response.data:
            return None
        row = response.data[0]
        if datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc):
            return None
        # Only succeeds if nobody used the link in the meantime.
        used = self._run(
            self.client.table("auth_tokens")
            .update({"used_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", row["id"])
            .is_("used_at", "null")
        )
        return int(row["user_id"]) if used.data else None

    def revoke_all(self, user_id: int, purpose: str) -> None:
        """Invalidate every unused link of this kind for the account."""
        self._run(
            self.client.table("auth_tokens")
            .update({"used_at": datetime.now(timezone.utc).isoformat()})
            .eq("user_id", user_id)
            .eq("purpose", purpose)
            .is_("used_at", "null")
        )


class RateLimiter(Repository):
    """Shared request counters (public.hit_rate_limit in auth_upgrade.sql).

    The counters live in the database, so every serverless instance sees the
    same totals.
    """

    def hit(self, key: str, window_seconds: int, limit: int) -> bool:
        """Count one hit. Return False when the key is over its limit."""
        response = self._run(self.client.rpc("hit_rate_limit", {
            "p_key": key[:300],
            "p_window_seconds": window_seconds,
            "p_limit": limit,
        }))
        return bool(response.data)


@lru_cache(maxsize=1)
def _create_client(url: str, key: str) -> Client:
    options = ClientOptions(
        postgrest_client_timeout=TIMEOUT_SECONDS,
        auto_refresh_token=False,
        persist_session=False,
    )
    return create_client(url, key, options=options)


def _get_client() -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_key:
        logger.error("SUPABASE_URL or SUPABASE_SECRET_KEY is not set.")
        raise DatabaseUnavailableError()
    try:
        client = _create_client(settings.supabase_url, settings.supabase_key)
    except Exception as error:
        logger.error("Could not create the Supabase client: %s", type(error).__name__)
        raise DatabaseUnavailableError() from error
    return client


def get_repository() -> GPURepository:
    """FastAPI dependency that gives each request a GPU repository."""
    return GPURepository(_get_client())


def get_user_repository() -> UserRepository:
    """FastAPI dependency that gives each request a user repository."""
    return UserRepository(_get_client())


def get_token_repository() -> TokenRepository:
    """FastAPI dependency for one-time email links."""
    return TokenRepository(_get_client())


def get_rate_limiter() -> RateLimiter:
    """FastAPI dependency for the shared rate limiter."""
    return RateLimiter(_get_client())


def get_image_store() -> ImageStore:
    """FastAPI dependency for GPU pictures in Supabase Storage."""
    return ImageStore(_get_client())
