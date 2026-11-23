"""GPU Nexus Marketplace: listings, photos and messages. Run with:  python -m pytest"""

import io

from PIL import Image

import market
from conftest import log_in

PHOTO_URL = "https://test-project.supabase.co/storage/v1/object/public/listing-photos/"
OTHER_EMAIL, OTHER_PASSWORD = "third@example.com", "third-password-1"


def photo(size=(2400, 1600)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, (30, 160, 90)).save(out, "JPEG")
    return out.getvalue()


def upload(client, headers=None, data=None):
    return client.post("/listings/photos", headers=headers or {},
                       files={"file": ("card.jpg", photo() if data is None else data, "image/jpeg")})


def make_listing(**changes) -> dict:
    return {"title": "RTX 3080 10GB, used for one year", "condition": "good",
            "price": 18500, "currency": "PHP", "location": "Quezon City", **changes}


def create(client, headers=None, **changes):
    return client.post("/listings", json=make_listing(**changes), headers=headers or {})


def third_user(api, anonymous) -> dict:
    api.insert_user(OTHER_EMAIL, OTHER_PASSWORD)
    return log_in(anonymous, OTHER_EMAIL, OTHER_PASSWORD)


# ---------- access ----------

def test_marketplace_needs_a_sign_in(anonymous):
    assert anonymous.get("/listings").status_code == 401
    assert anonymous.post("/listings", json=make_listing()).status_code == 401
    assert anonymous.get("/me/conversations").status_code == 401


# ---------- photos ----------

def test_photo_upload_is_resized_webp_named_for_the_seller(client, api):
    response = upload(client)
    assert response.status_code == 201, response.text
    url = response.json()["url"]
    assert url.startswith(PHOTO_URL + "u1-") and url.endswith(".webp")
    stored = Image.open(io.BytesIO(api.buckets["listing-photos"][url.removeprefix(PHOTO_URL)]))
    assert stored.format == "WEBP"
    assert max(stored.size) == market.PHOTO_MAX_SIDE      # 2400x1600 shrunk to 1600x1067


def test_photo_upload_refuses_files_that_are_not_pictures(client):
    response = upload(client, data=b"<script>alert(1)</script>")
    assert response.status_code == 422


def test_listing_only_takes_your_own_photos(client, anonymous, admin):
    mine = upload(client).json()["url"]
    theirs = upload(client, headers=admin).json()["url"]
    assert create(client, photos=[mine]).status_code == 201
    assert create(client, photos=[theirs]).status_code == 422
    assert create(client, photos=["https://evil.example/x.webp"]).status_code == 422


# ---------- listings ----------

def test_create_and_read_a_listing(client):
    created = create(client, gpu_id=1)
    assert created.status_code == 201, created.text
    listing = created.json()
    assert listing["status"] == "active"
    assert listing["seller"] == {"id": 1, "name": "user"}
    assert listing["is_mine"] is True
    assert listing["gpu"]["model"]
    assert client.get(f"/listings/{listing['id']}").json()["title"] == "RTX 3080 10GB, used for one year"


def test_listing_checks_its_fields(client):
    assert create(client, price=0).status_code == 422
    assert create(client, condition="broken").status_code == 422
    assert create(client, currency="EUR").status_code == 422
    assert create(client, title="x").status_code == 422
    assert create(client, gpu_id=999).status_code == 422
    assert create(client, photos=[f"{PHOTO_URL}u1-a.webp"] * 7).status_code == 422


def test_browse_shows_active_listings_and_mine_shows_sold_too(client, admin):
    keep = create(client).json()["id"]
    sold = create(client).json()["id"]
    client.patch(f"/listings/{sold}", json={"status": "sold"})
    create(client, headers=admin)

    browse = client.get("/listings").json()
    assert {item["id"] for item in browse["listings"]} == {keep, 3}
    mine = client.get("/listings", params={"mine": "true"}).json()
    assert {item["id"] for item in mine["listings"]} == {keep, sold}


def test_listings_for_one_gpu(client):
    create(client, gpu_id=1)
    create(client, gpu_id=2)
    only = client.get("/listings", params={"gpu_id": 1}).json()["listings"]
    assert [item["gpu_id"] for item in only] == [1]


def test_only_the_seller_can_edit_and_removed_photos_are_deleted(client, admin, api):
    first = upload(client).json()["url"]
    second = upload(client).json()["url"]
    listing = create(client, photos=[first, second]).json()

    assert client.patch(f"/listings/{listing['id']}", json={"price": 1}, headers=admin).status_code == 403
    updated = client.patch(f"/listings/{listing['id']}", json={"photos": [second], "price": 17000})
    assert updated.status_code == 200, updated.text
    assert updated.json()["photos"] == [second]
    assert updated.json()["price"] == 17000
    assert first.removeprefix(PHOTO_URL) not in api.buckets["listing-photos"]
    assert second.removeprefix(PHOTO_URL) in api.buckets["listing-photos"]


def test_delete_removes_the_listing_and_its_photos(client, admin, api):
    url = upload(client).json()["url"]
    listing = create(client, photos=[url]).json()
    # admins may remove any listing
    assert client.delete(f"/listings/{listing['id']}", headers=admin).status_code == 204
    assert client.get(f"/listings/{listing['id']}").status_code == 404
    assert url.removeprefix(PHOTO_URL) not in api.buckets["listing-photos"]


def test_other_users_cannot_delete_a_listing(client, anonymous, api):
    listing = create(client).json()
    other = third_user(api, anonymous)
    assert client.delete(f"/listings/{listing['id']}", headers=other).status_code == 403


# ---------- messages ----------

def test_buyer_and_seller_message_each_other(client, admin):
    listing = create(client).json()                       # seller: the user (id 1)
    buyer = admin                                         # buyer: the admin account (id 2)

    sent = client.post(f"/listings/{listing['id']}/messages", json={"body": "Is it still available?"}, headers=buyer)
    assert sent.status_code == 201, sent.text
    conversation_id = sent.json()["conversation_id"]

    # the seller sees one unread conversation
    assert client.get("/me/unread").json() == {"unread": 1}
    inbox = client.get("/me/conversations").json()
    assert inbox["conversations"][0]["role"] == "selling"
    assert inbox["conversations"][0]["with"]["name"] == "admin"
    assert inbox["conversations"][0]["last_body"] == "Is it still available?"

    # opening it marks it read
    opened = client.get(f"/conversations/{conversation_id}").json()
    assert [m["body"] for m in opened["messages"]] == ["Is it still available?"]
    assert opened["messages"][0]["mine"] is False
    assert client.get("/me/unread").json() == {"unread": 0}

    # the seller replies; now the buyer has one unread
    reply = client.post(f"/conversations/{conversation_id}/messages", json={"body": "Yes, meet-up in QC?"})
    assert reply.status_code == 201
    assert client.get("/me/unread", headers=buyer).json() == {"unread": 1}

    # a second message from the buyer continues the same conversation
    again = client.post(f"/listings/{listing['id']}/messages", json={"body": "Sure."}, headers=buyer)
    assert again.json()["conversation_id"] == conversation_id


def test_outsiders_cannot_read_or_join_a_conversation(client, admin, anonymous, api):
    listing = create(client).json()
    conversation_id = client.post(f"/listings/{listing['id']}/messages", json={"body": "Hi"},
                                  headers=admin).json()["conversation_id"]
    other = third_user(api, anonymous)
    assert client.get(f"/conversations/{conversation_id}", headers=other).status_code == 404
    assert client.post(f"/conversations/{conversation_id}/messages", json={"body": "x"},
                       headers=other).status_code == 404


def test_message_rules(client, admin):
    listing = create(client).json()
    assert client.post(f"/listings/{listing['id']}/messages", json={"body": "me"}).status_code == 409
    assert client.post(f"/listings/{listing['id']}/messages", json={"body": "   "}, headers=admin).status_code == 422
    client.patch(f"/listings/{listing['id']}", json={"status": "sold"})
    assert client.post(f"/listings/{listing['id']}/messages", json={"body": "hi"}, headers=admin).status_code == 409
    assert client.post("/listings/999/messages", json={"body": "hi"}, headers=admin).status_code == 404
