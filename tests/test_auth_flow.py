"""Sign-up, email verification, session cookie, lockout, password reset and
server-side sign-out. Run with:  python -m pytest"""

from datetime import datetime, timedelta, timezone

import auth
from conftest import (
    ADMIN_EMAIL, ADMIN_PASSWORD, USER_EMAIL, USER_PASSWORD, link_secret, log_in, make_gpu,
)
from security import SESSION_COOKIE

NEW = {"email": "fresh@gmail.com", "password": "fresh-password-1"}
CSRF = {"X-Requested-With": "fetch"}


def register_and_verify(anonymous, outbox, account=NEW):
    assert anonymous.post("/auth/register", json=account).status_code == 201
    assert anonymous.post("/auth/verify", json={"token": link_secret(outbox[-1])}).status_code == 200


# ==================== SIGN-UP AND VERIFICATION ====================

def test_register_emails_a_verification_link(anonymous, api, outbox):
    response = anonymous.post("/auth/register", json=NEW)
    assert response.status_code == 201
    assert response.json()["email_verified"] is False
    assert len(outbox) == 1
    assert outbox[0]["to"] == NEW["email"]
    assert "https://site.test/verify.html?token=" in outbox[0]["text"]
    # Only a hash of the link secret is stored.
    secret = link_secret(outbox[0])
    assert api.tokens[0]["token_hash"] == auth.hash_link_secret(secret)
    assert secret not in str(api.tokens)


def test_unverified_account_cannot_log_in(anonymous):
    anonymous.post("/auth/register", json=NEW)
    response = anonymous.post("/auth/login", json=NEW)
    assert response.status_code == 403
    assert "Confirm your email" in response.json()["detail"]
    assert SESSION_COOKIE not in response.cookies


def test_verification_link_works_once(anonymous, outbox):
    anonymous.post("/auth/register", json=NEW)
    body = {"token": link_secret(outbox[0])}
    assert anonymous.post("/auth/verify", json=body).status_code == 200
    again = anonymous.post("/auth/verify", json=body)
    assert again.status_code == 400
    assert again.json() == {"detail": "This link is invalid or has expired."}
    assert anonymous.post("/auth/login", json=NEW).status_code == 200


def test_expired_or_made_up_verification_link_is_rejected(anonymous, api, outbox):
    anonymous.post("/auth/register", json=NEW)
    api.tokens[0]["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    assert anonymous.post("/auth/verify", json={"token": link_secret(outbox[0])}).status_code == 400
    assert anonymous.post("/auth/verify", json={"token": "x" * 43}).status_code == 400
    assert anonymous.post("/auth/verify", json={"token": "bad token!"}).status_code == 422


def test_resend_verification_gives_the_same_answer_for_any_email(anonymous, outbox):
    anonymous.post("/auth/register", json=NEW)
    first_link = link_secret(outbox[0])
    known = anonymous.post("/auth/resend-verification", json={"email": NEW["email"]})
    unknown = anonymous.post("/auth/resend-verification", json={"email": "nobody@gmail.com"})
    verified = anonymous.post("/auth/resend-verification", json={"email": USER_EMAIL})
    assert known.status_code == unknown.status_code == verified.status_code == 202
    assert known.json() == unknown.json() == verified.json()
    assert len(outbox) == 2  # only the unverified account got a new link
    # The newer link replaces the older one.
    assert anonymous.post("/auth/verify", json={"token": first_link}).status_code == 400
    assert anonymous.post("/auth/verify", json={"token": link_secret(outbox[1])}).status_code == 200


def test_register_is_refused_when_email_is_not_configured(anonymous, api, monkeypatch):
    monkeypatch.delenv("GMAIL_APP_PASSWORD")
    response = anonymous.post("/auth/register", json=NEW)
    assert response.status_code == 503
    assert response.json() == {"detail": "Email is not configured on the server."}
    assert len(api.users) == 2


# ==================== SESSION COOKIE ====================

def test_login_sets_a_locked_down_session_cookie(anonymous):
    response = anonymous.post("/auth/login", json={"email": USER_EMAIL, "password": USER_PASSWORD})
    header = response.headers["set-cookie"]
    assert header.startswith(f"{SESSION_COOKIE}=")
    for flag in ("HttpOnly", "Secure", "SameSite=strict", "Path=/", "Max-Age=28800"):
        assert flag.lower() in header.lower()


def test_cookie_alone_lets_the_browser_read(anonymous):
    anonymous.post("/auth/login", json={"email": USER_EMAIL, "password": USER_PASSWORD})
    assert anonymous.get("/gpus").status_code == 200
    assert anonymous.get("/auth/me").json()["email"] == USER_EMAIL


def test_cookie_writes_need_the_csrf_header(anonymous, api):
    anonymous.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    blocked = anonymous.post("/gpus", json=make_gpu(model="RTX Csrf"))
    assert blocked.status_code == 403
    assert api.write_requests == []
    allowed = anonymous.post("/gpus", json=make_gpu(model="RTX Csrf"), headers=CSRF)
    assert allowed.status_code == 201


def test_logout_clears_the_cookie(anonymous):
    anonymous.post("/auth/login", json={"email": USER_EMAIL, "password": USER_PASSWORD})
    response = anonymous.post("/auth/logout")
    assert response.status_code == 204
    assert 'gpu_session=""' in response.headers["set-cookie"] or "Max-Age=0" in response.headers["set-cookie"]
    assert anonymous.get("/gpus").status_code == 401


def test_logout_everywhere_cancels_every_existing_token(anonymous):
    first = log_in(anonymous, USER_EMAIL, USER_PASSWORD)
    second = log_in(anonymous, USER_EMAIL, USER_PASSWORD)
    assert anonymous.post("/auth/logout-all", headers=first).status_code == 204
    assert anonymous.get("/gpus", headers=first).status_code == 401
    assert anonymous.get("/gpus", headers=second).status_code == 401
    fresh = log_in(anonymous, USER_EMAIL, USER_PASSWORD)
    assert anonymous.get("/gpus", headers=fresh).status_code == 200


def test_deleted_account_loses_access_immediately(anonymous, api):
    headers = log_in(anonymous, USER_EMAIL, USER_PASSWORD)
    api.users = [u for u in api.users if u["email"] != USER_EMAIL]
    assert anonymous.get("/gpus", headers=headers).status_code == 401


def test_demoted_admin_loses_admin_access_immediately(anonymous, api):
    headers = log_in(anonymous, ADMIN_EMAIL, ADMIN_PASSWORD)
    api.user(ADMIN_EMAIL)["role"] = "user"
    response = anonymous.post("/gpus", json=make_gpu(model="RTX Demoted"), headers=headers)
    assert response.status_code == 403
    assert api.write_requests == []


# ==================== LOCKOUT AND RATE LIMITS ====================

def wrong_login(anonymous):
    return anonymous.post("/auth/login", json={"email": USER_EMAIL, "password": "wrong-password"})


def test_five_wrong_passwords_lock_the_account(anonymous, api):
    for _ in range(4):
        assert wrong_login(anonymous).status_code == 401
    assert api.user(USER_EMAIL)["failed_logins"] == 4
    assert wrong_login(anonymous).status_code == 401
    assert api.user(USER_EMAIL)["locked_until"] is not None

    correct = anonymous.post("/auth/login", json={"email": USER_EMAIL, "password": USER_PASSWORD})
    assert correct.status_code == 429
    assert "locked" in correct.json()["detail"]


def test_lock_expires_and_a_good_login_resets_the_counter(anonymous, api):
    for _ in range(5):
        wrong_login(anonymous)
    api.user(USER_EMAIL)["locked_until"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    ).isoformat()
    wrong_login(anonymous)
    ok = anonymous.post("/auth/login", json={"email": USER_EMAIL, "password": USER_PASSWORD})
    assert ok.status_code == 200
    assert api.user(USER_EMAIL)["failed_logins"] == 0
    assert api.user(USER_EMAIL)["locked_until"] is None


def test_login_attempts_are_limited_per_network(anonymous, api):
    api.rate_limit_override["login-ip"] = 3
    for _ in range(3):
        assert wrong_login(anonymous).status_code == 401
    blocked = anonymous.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == str(15 * 60)


def test_signups_are_limited_per_network(anonymous, api):
    api.rate_limit_override["register-ip"] = 2
    for n in range(2):
        body = {"email": f"person{n}@gmail.com", "password": "long-password-1"}
        assert anonymous.post("/auth/register", json=body).status_code == 201
    third = anonymous.post("/auth/register", json={"email": "p3@gmail.com", "password": "long-password-1"})
    assert third.status_code == 429
    assert len(api.users) == 4


def test_reset_emails_are_limited_per_address(anonymous, api, outbox):
    for _ in range(3):
        anonymous.post("/auth/forgot-password", json={"email": USER_EMAIL})
    assert anonymous.post("/auth/forgot-password", json={"email": USER_EMAIL}).status_code == 429
    assert len(outbox) == 3


# ==================== PASSWORD RESET ====================

def test_forgot_password_answers_the_same_for_unknown_emails(anonymous, outbox):
    known = anonymous.post("/auth/forgot-password", json={"email": USER_EMAIL})
    unknown = anonymous.post("/auth/forgot-password", json={"email": "nobody@gmail.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert [mail["to"] for mail in outbox] == [USER_EMAIL]
    assert "https://site.test/reset.html?token=" in outbox[0]["text"]


def test_reset_password_changes_it_and_signs_out_everywhere(anonymous, outbox):
    old_session = log_in(anonymous, USER_EMAIL, USER_PASSWORD)
    anonymous.post("/auth/forgot-password", json={"email": USER_EMAIL})
    body = {"token": link_secret(outbox[0]), "password": "brand-new-password"}

    assert anonymous.post("/auth/reset-password", json=body).status_code == 200
    assert anonymous.get("/gpus", headers=old_session).status_code == 401
    old = anonymous.post("/auth/login", json={"email": USER_EMAIL, "password": USER_PASSWORD})
    assert old.status_code == 401
    new = anonymous.post("/auth/login", json={"email": USER_EMAIL, "password": "brand-new-password"})
    assert new.status_code == 200
    # The link works only once.
    assert anonymous.post("/auth/reset-password", json=body).status_code == 400


def test_reset_link_expires_after_30_minutes(anonymous, api, outbox):
    anonymous.post("/auth/forgot-password", json={"email": USER_EMAIL})
    expires = datetime.fromisoformat(api.tokens[0]["expires_at"])
    assert timedelta(minutes=29) < expires - datetime.now(timezone.utc) <= timedelta(minutes=30)
    api.tokens[0]["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    body = {"token": link_secret(outbox[0]), "password": "brand-new-password"}
    assert anonymous.post("/auth/reset-password", json=body).status_code == 400


def test_verify_link_cannot_be_used_to_reset_a_password(anonymous, outbox):
    anonymous.post("/auth/register", json=NEW)
    body = {"token": link_secret(outbox[0]), "password": "brand-new-password"}
    assert anonymous.post("/auth/reset-password", json=body).status_code == 400


def test_reset_password_unlocks_a_locked_account(anonymous, api, outbox):
    for _ in range(5):
        wrong_login(anonymous)
    anonymous.post("/auth/forgot-password", json={"email": USER_EMAIL})
    body = {"token": link_secret(outbox[0]), "password": "brand-new-password"}
    anonymous.post("/auth/reset-password", json=body)
    ok = anonymous.post("/auth/login", json={"email": USER_EMAIL, "password": "brand-new-password"})
    assert ok.status_code == 200


def test_full_sign_up_flow(anonymous, outbox):
    register_and_verify(anonymous, outbox)
    anonymous.post("/auth/login", json=NEW)
    assert anonymous.get("/auth/me").json()["email_verified"] is True
    assert anonymous.get("/gpus").json()["count"] == 3
