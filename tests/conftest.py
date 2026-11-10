"""Shared test setup.

The tests never touch the real Supabase project. The Supabase SDK is given a
simulated Data API (FakeDataAPI) that receives the real HTTP requests the SDK
builds and answers them from a list kept in memory.
"""

import json
import re

import httpx
import pytest
from fastapi.testclient import TestClient
from supabase import ClientOptions, create_client

import auth
from database import GPURepository, UserRepository, get_repository, get_user_repository
from index import app

SUPABASE_TEST_KEY = "test-secret-key"
AUTH_TEST_SECRET = "test-auth-secret-with-more-than-32-characters"
USER_EMAIL, USER_PASSWORD = "user@example.com", "user-password-1"
ADMIN_EMAIL, ADMIN_PASSWORD = "admin@example.com", "admin-password-1"

SEARCH_COLUMNS = [
    "brand", "manufacturer", "model", "series", "architecture", "vram",
    "memory_type", "cuda_cores", "core_type", "memory_bus", "power",
    "base_clock", "boost_clock", "recommended_psu", "pcie_interface",
    "description",
]


def make_gpu(**changes) -> dict:
    """A valid GPU body. Pass keyword arguments to change fields."""
    gpu = {
        "brand": "NVIDIA",
        "manufacturer": "NVIDIA",
        "model": "GeForce RTX Test",
        "series": "GeForce RTX",
        "architecture": "Test",
        "vram": "8GB GDDR6",
        "memory_type": "GDDR6",
        "cuda_cores": 1000,
        "core_count": 1000,
        "core_type": "CUDA Cores",
        "memory_bus": "128-bit",
        "memory_bandwidth_gbps": 100.0,
        "power": "100W",
        "base_clock": "1 GHz",
        "boost_clock": "2 GHz",
        "recommended_psu": "400W",
        "process_node_nm": 8,
        "pcie_interface": "PCIe 4.0 x16",
        "launch_price_usd": 100.0,
        "release_date": "2025-01-01",
        "description": "A test catalog entry.",
    }
    gpu.update(changes)
    return gpu


# Three rows that are in the simulated database before each test.
SEED_GPUS = [
    make_gpu(
        model="GeForce RTX 5090", series="GeForce RTX 50 Series",
        architecture="Blackwell", vram="32GB GDDR7", memory_type="GDDR7",
        release_date="2025-01-30", description="NVIDIA's flagship GeForce graphics card.",
    ),
    make_gpu(
        model="GeForce RTX 4090", series="GeForce RTX 40 Series",
        architecture="Ada Lovelace", vram="24GB GDDR6X", memory_type="GDDR6X",
        release_date="2022-10-12", description="A previous-generation flagship GeForce GPU.",
    ),
    make_gpu(
        model="GeForce GTX 1080 Ti", series="GeForce GTX 10 Series",
        architecture="Pascal", vram="11GB GDDR5X", memory_type="GDDR5X",
        release_date="2017-03-10", description="A high-end Pascal GPU with 100% more memory_bus tests.",
    ),
]


def like_to_regex(pattern: str) -> re.Pattern:
    """Turn a SQL LIKE pattern into a regular expression."""
    parts, i = [], 0
    while i < len(pattern):
        char = pattern[i]
        if char == "\\" and i + 1 < len(pattern):
            parts.append(re.escape(pattern[i + 1]))
            i += 2
            continue
        if char in "%*":
            parts.append(".*")
        elif char == "_":
            parts.append(".")
        else:
            parts.append(re.escape(char))
        i += 1
    return re.compile("^" + "".join(parts) + "$", re.IGNORECASE | re.DOTALL)


class FakeDataAPI:
    """A simulated Supabase Data API for the gpus and users tables."""

    def __init__(self):
        self.rows: list[dict] = []          # the gpus table
        self.next_id = 1
        self.users: list[dict] = []         # the users table
        self.next_user_id = 1
        self.requests: list[tuple[str, str]] = []
        self.max_rows: int | None = None   # server page limit, like Supabase "Max rows"
        self.failure: str | None = None    # "timeout" or "error"

    # ----- data helpers -----

    def insert(self, gpu: dict) -> dict:
        row = {key: value for key, value in gpu.items() if key != "search_text"}
        row["id"] = self.next_id
        self.next_id += 1
        row["search_text"] = " ".join(str(row[c]) for c in SEARCH_COLUMNS).lower()
        self.rows.append(row)
        return row

    def is_duplicate(self, gpu: dict, ignore_id=None) -> bool:
        def key(row):
            return tuple(row[c].lower() for c in ("brand", "manufacturer", "model"))
        return any(key(row) == key(gpu) and row["id"] != ignore_id for row in self.rows)

    def insert_user(self, email: str, password: str, role: str = "user") -> dict:
        user = {
            "id": self.next_user_id,
            "email": email,
            "password_hash": auth.hash_password(password),
            "role": role,
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        self.next_user_id += 1
        self.users.append(user)
        return user

    @property
    def gpu_requests(self) -> list[tuple[str, str]]:
        return [r for r in self.requests if "/rest/v1/gpus" in r[1]]

    @property
    def write_requests(self) -> list[tuple[str, str]]:
        return [r for r in self.gpu_requests if r[0] in ("POST", "PATCH", "DELETE")]

    def handle_users(self, request: httpx.Request) -> httpx.Response:
        """The users table: look up by id or email, and insert."""
        params = request.url.params
        if request.method == "GET":
            rows = list(self.users)
            for column in ("id", "email"):
                if column in params:
                    operator, value = params[column].split(".", 1)
                    assert operator == "eq"
                    rows = [row for row in rows if str(row[column]) == value]
            wanted = params["select"].split(",")
            return httpx.Response(200, json=[{c: row[c] for c in wanted} for row in rows])
        if request.method == "POST":
            new = json.loads(request.content)
            if any(row["email"] == new["email"] for row in self.users):
                return httpx.Response(409, json={
                    "code": "23505", "details": "Key (email) already exists.", "hint": None,
                    "message": 'duplicate key value violates unique constraint "users_email_key"',
                })
            user = {
                "id": self.next_user_id, "email": new["email"],
                "password_hash": new["password_hash"], "role": "user",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
            self.next_user_id += 1
            self.users.append(user)
            return httpx.Response(201, json=[user])
        return httpx.Response(405, json={"message": "method not allowed"})

    # ----- request handling -----

    def matching_rows(self, params) -> list[dict]:
        rows = list(self.rows)
        if "id" in params:
            operator, value = params["id"].split(".", 1)
            assert operator == "eq"
            rows = [row for row in rows if row["id"] == int(value)]
        if "search_text" in params:
            operator, value = params["search_text"].split(".", 1)
            assert operator == "ilike"
            regex = like_to_regex(value)
            rows = [row for row in rows if regex.match(row["search_text"])]
        return rows

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append((request.method, str(request.url)))
        if self.failure == "timeout":
            raise httpx.ConnectTimeout("simulated timeout", request=request)
        if self.failure == "error":
            return httpx.Response(500, json={
                "code": "XX000", "details": "host=db.internal password=hunter2",
                "hint": None, "message": "internal database failure",
            })

        assert request.headers["apikey"] == SUPABASE_TEST_KEY
        if request.url.path == "/rest/v1/users":
            return self.handle_users(request)
        assert request.url.path == "/rest/v1/gpus"
        params = request.url.params
        prefer = request.headers.get("prefer", "")

        if request.method == "GET":
            rows = self.matching_rows(params)
            if params.get("order") == "id.asc":
                rows.sort(key=lambda row: row["id"])
            total = len(rows)
            offset = int(params.get("offset", 0))
            limit = int(params["limit"]) if "limit" in params else total
            if self.max_rows is not None:
                limit = min(limit, self.max_rows)
            page = rows[offset:offset + limit]
            columns = params.get("select", "*")
            if columns != "*":
                wanted = columns.split(",")
                page = [{c: row[c] for c in wanted} for row in page]
            headers = {}
            if "count=exact" in prefer:
                span = f"{offset}-{offset + len(page) - 1}" if page else "*"
                headers["content-range"] = f"{span}/{total}"
            status = 206 if headers and len(page) < total else 200
            return httpx.Response(status, json=page, headers=headers)

        if request.method == "POST":
            gpu = json.loads(request.content)
            if self.is_duplicate(gpu):
                return self.duplicate_response()
            return httpx.Response(201, json=[self.insert(gpu)])

        if request.method == "PATCH":
            changes = json.loads(request.content)
            rows = self.matching_rows(params)
            for row in rows:
                if self.is_duplicate({**row, **changes}, ignore_id=row["id"]):
                    return self.duplicate_response()
                row.update(changes)
                row["search_text"] = " ".join(str(row[c]) for c in SEARCH_COLUMNS).lower()
            return httpx.Response(200, json=rows)

        if request.method == "DELETE":
            rows = self.matching_rows(params)
            self.rows = [row for row in self.rows if row not in rows]
            return httpx.Response(200, json=rows)

        return httpx.Response(405, json={"message": "method not allowed"})

    @staticmethod
    def duplicate_response() -> httpx.Response:
        return httpx.Response(409, json={
            "code": "23505",
            "details": "Key (lower(brand), lower(manufacturer), lower(model)) already exists.",
            "hint": None,
            "message": 'duplicate key value violates unique constraint "gpus_brand_manufacturer_model_key"',
        })


@pytest.fixture(autouse=True)
def fast_test_settings(monkeypatch):
    """A test signing secret, and quick password hashing so the tests run fast."""
    monkeypatch.setenv("AUTH_SECRET", AUTH_TEST_SECRET)
    monkeypatch.setattr(auth, "PBKDF2_ITERATIONS", 1_000)


@pytest.fixture
def api() -> FakeDataAPI:
    """The simulated database: three seed GPUs (IDs 1 to 3), one user and one admin."""
    fake = FakeDataAPI()
    for gpu in SEED_GPUS:
        fake.insert(gpu)
    fake.insert_user(USER_EMAIL, USER_PASSWORD)             # id 1
    fake.insert_user(ADMIN_EMAIL, ADMIN_PASSWORD, "admin")  # id 2
    return fake


@pytest.fixture
def anonymous(api):
    """A test client that is not logged in."""
    http_client = httpx.Client(transport=httpx.MockTransport(api.handler))
    supabase = create_client(
        "https://test-project.supabase.co",
        SUPABASE_TEST_KEY,
        options=ClientOptions(
            httpx_client=http_client, auto_refresh_token=False, persist_session=False
        ),
    )
    app.dependency_overrides[get_repository] = lambda: GPURepository(supabase)
    app.dependency_overrides[get_user_repository] = lambda: UserRepository(supabase)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def log_in(test_client, email: str, password: str) -> dict:
    """Log in through the API and return the Authorization header."""
    response = test_client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def client(anonymous, api):
    """A test client logged in as a regular user."""
    anonymous.headers.update(log_in(anonymous, USER_EMAIL, USER_PASSWORD))
    api.requests.clear()
    return anonymous


@pytest.fixture
def admin(anonymous) -> dict:
    """Headers for a request made by the admin account."""
    return log_in(anonymous, ADMIN_EMAIL, ADMIN_PASSWORD)
