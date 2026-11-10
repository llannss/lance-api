"""Database access for the GPU catalog and the user accounts.

All Supabase queries live in GPURepository and UserRepository, so the
endpoint functions in index.py never talk to the database directly.
"""

import logging
from functools import lru_cache

from supabase import Client, ClientOptions, PostgrestAPIError, create_client

from config import get_settings

logger = logging.getLogger("gpu_api.database")

# The columns the API returns. search_text is left out on purpose.
COLUMNS = (
    "id,brand,manufacturer,model,series,architecture,vram,memory_type,"
    "cuda_cores,core_count,core_type,memory_bus,memory_bandwidth_gbps,power,"
    "base_clock,boost_clock,recommended_psu,process_node_nm,pcie_interface,"
    "launch_price_usd,release_date,description"
)

# The account columns the API returns. password_hash is left out on purpose.
USER_COLUMNS = "id,email,role,created_at"

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

    def delete(self, gpu_id: int) -> bool:
        response = self._run(self.client.table("gpus").delete().eq("id", gpu_id))
        return bool(response.data)


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
