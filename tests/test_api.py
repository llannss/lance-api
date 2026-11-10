"""API tests. Run them with:  python -m pytest"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

import auth
import database
from conftest import (
    ADMIN_EMAIL, AUTH_TEST_SECRET, USER_EMAIL, USER_PASSWORD, make_gpu,
)


# ==================== READ ====================

def test_home_shows_api_information(anonymous):
    response = anonymous.get("/")
    assert response.status_code == 200
    assert response.json()["version"] == "2.0.0"
    assert "POST /gpus" in response.json()["endpoints"]


def test_health_reports_database_connected(anonymous):
    response = anonymous.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["database"] == "connected"


def test_list_returns_every_gpu_in_id_order(client):
    response = client.get("/gpus")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 3
    assert [gpu["id"] for gpu in body["gpus"]] == [1, 2, 3]
    assert "search_text" not in body["gpus"][0]


def test_list_is_empty_when_database_has_no_rows(client, api):
    api.rows.clear()
    assert client.get("/gpus").json() == {"count": 0, "gpus": []}


def test_get_gpu_by_id(client):
    response = client.get("/gpus/1")
    assert response.status_code == 200
    assert response.json()["model"] == "GeForce RTX 5090"
    assert response.json()["release_date"] == "2025-01-30"


def test_get_missing_gpu_returns_404(client):
    response = client.get("/gpus/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "GPU not found."}


def test_get_gpu_rejects_invalid_id(client):
    for gpu_id in ("abc", "0", "-1"):
        assert client.get(f"/gpus/{gpu_id}").status_code == 422


def test_logged_in_user_can_read_every_gpu_endpoint(client):
    for path in ("/gpus", "/gpus/1", "/gpus/search?q=rtx"):
        assert client.get(path).status_code == 200


# ==================== SEARCH ====================

def test_search_ignores_case(client):
    for keyword in ("rtx", "RTX", "rTx"):
        body = client.get("/gpus/search", params={"q": keyword}).json()
        assert body["query"] == "rtx"
        assert body["count"] == 2
        assert [gpu["model"] for gpu in body["results"]] == ["GeForce RTX 5090", "GeForce RTX 4090"]


def test_search_matches_other_gpu_details(client):
    assert client.get("/gpus/search", params={"q": "pascal"}).json()["count"] == 1
    assert client.get("/gpus/search", params={"q": "flagship"}).json()["count"] == 2
    assert client.get("/gpus/search", params={"q": "gddr7"}).json()["count"] == 1


def test_search_without_matches_returns_empty_list(client):
    response = client.get("/gpus/search", params={"q": "radeon"})
    assert response.status_code == 200
    assert response.json() == {"query": "radeon", "count": 0, "results": []}


def test_search_requires_a_keyword(client):
    assert client.get("/gpus/search").status_code == 422
    assert client.get("/gpus/search", params={"q": ""}).status_code == 422
    assert client.get("/gpus/search", params={"q": "   "}).status_code == 422


def test_search_treats_wildcard_characters_as_text(client):
    # Only the GTX 1080 Ti description contains "100%" and "memory_bus".
    assert client.get("/gpus/search", params={"q": "100%"}).json()["count"] == 1
    assert client.get("/gpus/search", params={"q": "memory_bus"}).json()["count"] == 1
    assert client.get("/gpus/search", params={"q": "r_x"}).json()["count"] == 0


# ==================== CREATE ====================

def test_create_gpu_returns_201_with_generated_id(client, admin):
    response = client.post("/gpus", json=make_gpu(), headers=admin)
    assert response.status_code == 201
    assert response.json()["id"] == 4
    assert response.json()["model"] == "GeForce RTX Test"
    assert response.headers["location"] == "/gpus/4"


def test_created_gpu_can_be_read_through_another_endpoint(client, admin):
    created = client.post("/gpus", json=make_gpu(), headers=admin).json()
    fetched = client.get(f"/gpus/{created['id']}").json()
    assert fetched == created


def test_created_gpu_appears_in_list_and_search(client, admin):
    client.post("/gpus", json=make_gpu(), headers=admin)
    assert client.get("/gpus").json()["count"] == 4
    results = client.get("/gpus/search", params={"q": "rtx test"}).json()["results"]
    assert [gpu["model"] for gpu in results] == ["GeForce RTX Test"]


def test_create_ignores_an_id_sent_by_the_client(client, admin):
    response = client.post("/gpus", json=make_gpu(id=500), headers=admin)
    assert response.status_code == 201
    assert response.json()["id"] == 4


def test_create_accepts_missing_launch_price(client, admin):
    body = make_gpu()
    del body["launch_price_usd"]
    response = client.post("/gpus", json=body, headers=admin)
    assert response.status_code == 201
    assert response.json()["launch_price_usd"] is None


def test_create_duplicate_returns_409(client, admin):
    client.post("/gpus", json=make_gpu(), headers=admin)
    response = client.post("/gpus", json=make_gpu(), headers=admin)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]
    # The same model in different letter case is still a duplicate.
    response = client.post("/gpus", json=make_gpu(model="geforce rtx 5090"), headers=admin)
    assert response.status_code == 409
    assert client.get("/gpus").json()["count"] == 4


# ==================== UPDATE ====================

def test_update_returns_the_updated_gpu(client, admin):
    response = client.put("/gpus/2", json=make_gpu(description="Updated description."), headers=admin)
    assert response.status_code == 200
    assert response.json()["id"] == 2
    assert response.json()["description"] == "Updated description."


def test_update_is_saved_for_later_requests(client, admin):
    client.put("/gpus/2", json=make_gpu(description="Updated description."), headers=admin)
    assert client.get("/gpus/2").json()["description"] == "Updated description."


def test_update_cannot_change_the_id(client, admin):
    response = client.put("/gpus/2", json=make_gpu(id=77), headers=admin)
    assert response.json()["id"] == 2
    assert client.get("/gpus/77").status_code == 404


def test_update_missing_gpu_returns_404(client, admin):
    response = client.put("/gpus/999", json=make_gpu(), headers=admin)
    assert response.status_code == 404
    assert response.json() == {"detail": "GPU not found."}


def test_update_to_an_existing_gpu_returns_409(client, admin):
    response = client.put("/gpus/2", json=make_gpu(model="GeForce RTX 5090"), headers=admin)
    assert response.status_code == 409


def test_update_rejects_invalid_body(client, admin):
    response = client.put("/gpus/2", json=make_gpu(brand="Voodoo"), headers=admin)
    assert response.status_code == 422
    assert client.get("/gpus/2").json()["brand"] == "NVIDIA"


# ==================== DELETE ====================

def test_delete_returns_204(client, admin):
    response = client.delete("/gpus/3", headers=admin)
    assert response.status_code == 204
    assert response.content == b""


def test_deleted_gpu_is_gone_afterwards(client, admin):
    client.delete("/gpus/3", headers=admin)
    assert client.get("/gpus/3").status_code == 404
    assert client.get("/gpus").json()["count"] == 2


def test_delete_missing_gpu_returns_404(client, admin):
    assert client.delete("/gpus/999", headers=admin).status_code == 404


# ==================== VALIDATION ====================

@pytest.mark.parametrize("changes", [
    {"model": ""},
    {"brand": "Voodoo"},
    {"memory_type": "DDR9"},
    {"cuda_cores": -1},
    {"cuda_cores": "many"},
    {"memory_bandwidth_gbps": 0},
    {"launch_price_usd": -5},
    {"release_date": "not a date"},
], ids=lambda changes: "-".join(f"{k}={str(v)[:10]!r}" for k, v in changes.items()))
def test_create_rejects_invalid_values(client, admin, api, changes):
    response = client.post("/gpus", json=make_gpu(**changes), headers=admin)
    assert response.status_code == 422
    assert api.write_requests == []


def test_create_rejects_blank_or_overlong_text(client, admin):
    for changes in ({"model": "   "}, {"model": "x" * 121}, {"description": "x" * 4001}):
        assert client.post("/gpus", json=make_gpu(**changes), headers=admin).status_code == 422


def test_create_rejects_missing_model(client, admin):
    body = make_gpu()
    del body["model"]
    response = client.post("/gpus", json=body, headers=admin)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "model"]


def test_create_rejects_malformed_json(client, admin):
    headers = {**admin, "Content-Type": "application/json"}
    response = client.post("/gpus", content='{"brand": "NVIDIA",', headers=headers)
    assert response.status_code == 422


def test_create_rejects_empty_body(client, admin):
    assert client.post("/gpus", headers=admin).status_code == 422


# ==================== ACCOUNTS ====================

NEW_ACCOUNT = {"email": "new@example.com", "password": "new-password-1"}


def test_register_creates_a_user_account(anonymous, api):
    response = anonymous.post("/auth/register", json=NEW_ACCOUNT)
    assert response.status_code == 201
    assert response.json()["email"] == "new@example.com"
    assert response.json()["role"] == "user"
    assert "password" not in response.text
    stored = api.users[-1]["password_hash"]
    assert stored.startswith("pbkdf2_sha256$") and "new-password-1" not in stored


def test_register_duplicate_email_returns_409(anonymous):
    anonymous.post("/auth/register", json=NEW_ACCOUNT)
    again = {"email": "  NEW@Example.com ", "password": "another-password"}
    response = anonymous.post("/auth/register", json=again)
    assert response.status_code == 409
    assert response.json() == {"detail": "An account with this email already exists."}


def test_register_rejects_invalid_email_or_short_password(anonymous, api):
    for body in (
        {"email": "not-an-email", "password": "long-enough-1"},
        {"email": "new@example.com", "password": "short"},
        {"email": "new@example.com"},
    ):
        assert anonymous.post("/auth/register", json=body).status_code == 422
    assert len(api.users) == 2


def test_register_cannot_choose_the_admin_role(anonymous):
    response = anonymous.post("/auth/register", json={**NEW_ACCOUNT, "role": "admin"})
    assert response.status_code == 201
    assert response.json()["role"] == "user"


def test_login_returns_a_token_and_the_account(anonymous):
    response = anonymous.post("/auth/login", json={"email": USER_EMAIL, "password": USER_PASSWORD})
    body = response.json()
    assert response.status_code == 200
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 8 * 60 * 60
    assert body["user"]["email"] == USER_EMAIL
    assert "password" not in response.text


def test_new_account_can_log_in_and_browse(anonymous):
    anonymous.post("/auth/register", json=NEW_ACCOUNT)
    token = anonymous.post("/auth/login", json=NEW_ACCOUNT).json()["access_token"]
    response = anonymous.get("/gpus", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["count"] == 3


def test_login_fails_the_same_way_for_wrong_password_and_unknown_email(anonymous):
    wrong_password = anonymous.post("/auth/login", json={"email": USER_EMAIL, "password": "wrong-password"})
    unknown_email = anonymous.post("/auth/login", json={"email": "nobody@example.com", "password": USER_PASSWORD})
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json() == {"detail": "Invalid email or password."}


def test_me_returns_the_logged_in_account(client):
    response = client.get("/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == USER_EMAIL
    assert response.json()["role"] == "user"


# ==================== SECURITY ====================

READ_PATHS = ["/gpus", "/gpus/1", "/gpus/search?q=rtx", "/auth/me"]
WRITE_REQUESTS = [("POST", "/gpus"), ("PUT", "/gpus/1"), ("DELETE", "/gpus/1")]


def test_public_endpoints_need_no_login(anonymous):
    assert anonymous.get("/").status_code == 200
    assert anonymous.get("/health").status_code == 200


def test_reading_without_login_returns_401(anonymous, api):
    for path in READ_PATHS:
        response = anonymous.get(path)
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
    assert api.requests == []


@pytest.mark.parametrize("method,path", WRITE_REQUESTS)
def test_write_without_login_returns_401(anonymous, api, method, path):
    response = anonymous.request(method, path, json=make_gpu())
    assert response.status_code == 401
    assert api.requests == []


@pytest.mark.parametrize("method,path", WRITE_REQUESTS)
def test_write_as_regular_user_returns_403(client, api, method, path):
    response = client.request(method, path, json=make_gpu())
    assert response.status_code == 403
    assert response.json() == {"detail": "Admin access is required."}
    assert api.requests == []


def test_invalid_tokens_are_rejected(anonymous, api):
    expired = jwt.encode(
        {"sub": "2", "email": ADMIN_EMAIL, "role": "admin",
         "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        AUTH_TEST_SECRET, algorithm="HS256",
    )
    forged = jwt.encode(
        {"sub": "2", "email": ADMIN_EMAIL, "role": "admin",
         "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "a-different-secret-that-is-also-32-characters", algorithm="HS256",
    )
    for token in ("not-a-token", expired, forged):
        response = anonymous.get("/gpus", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
    assert api.requests == []


def test_legacy_api_key_no_longer_works(anonymous, api):
    assert anonymous.get("/gpus", headers={"x-api-key": "apinilance"}).status_code == 401
    assert anonymous.post("/gpus", json=make_gpu(), headers={"x-api-key": "apinilance"}).status_code == 401
    assert api.requests == []


def test_rejected_writes_change_nothing(client):
    client.delete("/gpus/1")
    client.put("/gpus/1", json=make_gpu(description="Hacked."))
    assert client.get("/gpus/1").json()["description"] == "NVIDIA's flagship GeForce graphics card."
    assert client.get("/gpus").json()["count"] == 3


def test_login_is_refused_when_auth_secret_is_not_configured(anonymous, monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", "too-short")
    response = anonymous.post("/auth/login", json={"email": USER_EMAIL, "password": USER_PASSWORD})
    assert response.status_code == 503
    assert response.json() == {"detail": "Login is not configured on the server."}


def test_password_hashes_are_salted_and_verifiable():
    first, second = auth.hash_password("same-password"), auth.hash_password("same-password")
    assert first != second
    assert auth.verify_password("same-password", first)
    assert not auth.verify_password("other-password", first)
    assert not auth.verify_password("same-password", "not-a-hash")


# ==================== DATABASE FAILURES ====================

def test_database_timeout_returns_503(client, api):
    api.failure = "timeout"
    response = client.get("/gpus")
    assert response.status_code == 503
    assert response.json() == {"detail": "The database is currently unavailable. Please try again later."}


def test_database_error_does_not_leak_details(client, api, admin):
    api.failure = "error"
    response = client.post("/gpus", json=make_gpu(), headers=admin)
    assert response.status_code == 503
    assert "password" not in response.text
    assert "internal" not in response.text


def test_health_reports_unavailable_database(anonymous, api):
    api.failure = "timeout"
    response = anonymous.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"
    assert response.json()["database"] == "unavailable"


def test_missing_database_settings_return_503(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "")
    with pytest.raises(database.DatabaseUnavailableError):
        database.get_repository()


# ==================== PAGING ====================

def test_list_reads_every_row_when_server_limits_page_size(client, api):
    api.insert(make_gpu(model="Paging Test A"))
    api.insert(make_gpu(model="Paging Test B"))
    api.max_rows = 2
    body = client.get("/gpus").json()
    assert body["count"] == 5
    assert [gpu["id"] for gpu in body["gpus"]] == [1, 2, 3, 4, 5]
    assert len(api.gpu_requests) == 3


def test_search_reads_every_match_when_server_limits_page_size(client, api):
    api.max_rows = 1
    assert client.get("/gpus/search", params={"q": "geforce"}).json()["count"] == 3
