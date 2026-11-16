"""Recently viewed, saved comparisons and the admin activity log.
Run with:  python -m pytest"""

import database
from conftest import ADMIN_EMAIL, ADMIN_PASSWORD, USER_EMAIL, log_in, make_gpu


# ==================== RECENTLY VIEWED ====================

def test_recently_viewed_is_newest_first_without_duplicates(client):
    for gpu_id in (1, 2, 3, 1):
        assert client.post(f"/me/recent/{gpu_id}").status_code == 204
    body = client.get("/me/recent").json()
    assert [g["id"] for g in body["gpus"]] == [1, 3, 2]
    assert body["count"] == 3


def test_recently_viewed_keeps_only_the_newest(client, api, admin, monkeypatch):
    monkeypatch.setattr(database.RecentRepository, "KEEP", 2)
    for gpu_id in (1, 2, 3):
        client.post(f"/me/recent/{gpu_id}")
    assert [g["id"] for g in client.get("/me/recent").json()["gpus"]] == [3, 2]
    assert len(api.tables["recently_viewed"]) == 2


def test_recently_viewed_can_be_cleared_and_is_private(anonymous, client):
    client.post("/me/recent/1")
    admin = log_in(anonymous, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert anonymous.get("/me/recent", headers=admin).json()["count"] == 0
    assert client.delete("/me/recent").status_code == 204
    assert client.get("/me/recent").json()["count"] == 0


def test_recently_viewed_rejects_unknown_gpus_and_needs_login(anonymous, client):
    assert client.post("/me/recent/999").status_code == 404
    client.headers.pop("Authorization")
    assert client.get("/me/recent").status_code == 401
    assert client.post("/me/recent/1").status_code == 401


# ==================== SAVED COMPARISONS ====================

def test_save_list_and_delete_a_comparison(client):
    saved = client.post("/me/comparisons", json={"gpu_a_id": 1, "gpu_b_id": 2, "name": "  Flagships  "})
    assert saved.status_code == 201
    body = saved.json()
    assert body["name"] == "Flagships"
    assert (body["gpu_a_model"], body["gpu_b_model"]) == ("GeForce RTX 5090", "GeForce RTX 4090")

    listed = client.get("/me/comparisons").json()
    assert listed["count"] == 1 and listed["comparisons"][0]["id"] == body["id"]

    assert client.delete(f"/me/comparisons/{body['id']}").status_code == 204
    assert client.get("/me/comparisons").json()["count"] == 0


def test_saving_the_same_pair_again_returns_the_existing_one(client, api):
    first = client.post("/me/comparisons", json={"gpu_a_id": 1, "gpu_b_id": 2}).json()
    again = client.post("/me/comparisons", json={"gpu_a_id": 2, "gpu_b_id": 1})
    assert again.status_code == 200
    assert again.json()["id"] == first["id"]
    assert len(api.tables["saved_comparisons"]) == 1


def test_comparison_needs_two_different_existing_gpus(client):
    assert client.post("/me/comparisons", json={"gpu_a_id": 1, "gpu_b_id": 1}).status_code == 422
    assert client.post("/me/comparisons", json={"gpu_a_id": 1, "gpu_b_id": 999}).status_code == 404
    long_name = {"gpu_a_id": 1, "gpu_b_id": 2, "name": "x" * 81}
    assert client.post("/me/comparisons", json=long_name).status_code == 422


def test_comparisons_are_private_to_each_account(anonymous, client):
    mine = client.post("/me/comparisons", json={"gpu_a_id": 1, "gpu_b_id": 2}).json()
    admin = log_in(anonymous, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert anonymous.get("/me/comparisons", headers=admin).json()["count"] == 0
    # Someone else's ID can't be deleted.
    assert anonymous.delete(f"/me/comparisons/{mine['id']}", headers=admin).status_code == 404
    assert client.get("/me/comparisons").json()["count"] == 1


def test_comparisons_need_a_login(anonymous):
    assert anonymous.get("/me/comparisons").status_code == 401
    assert anonymous.post("/me/comparisons", json={"gpu_a_id": 1, "gpu_b_id": 2}).status_code == 401


# ==================== ADMIN ACTIVITY LOG ====================

def actions(client, admin):
    return [(e["action"], e["gpu_model"]) for e in client.get("/admin/audit", headers=admin).json()["entries"]]


def test_every_admin_change_is_logged_newest_first(client, admin):
    created = client.post("/gpus", json=make_gpu(model="RTX Audit"), headers=admin).json()
    client.put(f"/gpus/{created['id']}", json=make_gpu(model="RTX Audit", description="Changed."), headers=admin)
    client.delete(f"/gpus/{created['id']}", headers=admin)

    assert actions(client, admin) == [
        ("gpu.delete", "RTX Audit"),
        ("gpu.update", "RTX Audit"),
        ("gpu.create", "RTX Audit"),
    ]


def test_updates_record_what_changed_and_who_did_it(client, admin):
    client.put("/gpus/1", json=make_gpu(model="GeForce RTX 5090", vram="32GB GDDR7",
               description="Rewritten.", series="GeForce RTX 50 Series", architecture="Blackwell",
               memory_type="GDDR7", release_date="2025-01-30"), headers=admin)
    entry = client.get("/admin/audit", headers=admin).json()["entries"][0]
    assert entry["admin_email"] == ADMIN_EMAIL
    assert entry["changes"] == {"description": ["NVIDIA's flagship GeForce graphics card.", "Rewritten."]}


def test_an_update_that_changes_nothing_is_not_logged(client, admin):
    same = client.get("/gpus/2").json()
    same.pop("id"), same.pop("image_url")
    client.put("/gpus/2", json=same, headers=admin)
    assert actions(client, admin) == []


def test_picture_changes_are_logged(client, admin):
    import io
    from PIL import Image
    data = io.BytesIO()
    Image.new("RGB", (40, 30), (1, 2, 3)).save(data, "PNG")
    client.post("/gpus/1/image", headers=admin, files={"file": ("c.png", data.getvalue(), "image/png")})
    client.delete("/gpus/1/image", headers=admin)
    client.delete("/gpus/1/image", headers=admin)   # nothing left to remove: not logged
    assert actions(client, admin) == [
        ("image.remove", "GeForce RTX 5090"),
        ("image.upload", "GeForce RTX 5090"),
    ]


def test_failed_writes_are_not_logged(client, admin):
    client.post("/gpus", json=make_gpu(model="GeForce RTX 5090"), headers=admin)   # duplicate
    client.put("/gpus/999", json=make_gpu(), headers=admin)                       # missing
    assert actions(client, admin) == []


def test_only_admins_can_read_the_log(anonymous, client, api):
    assert client.get("/admin/audit").status_code == 403
    client.headers.pop("Authorization")
    assert client.get("/admin/audit").status_code == 401


def test_the_log_pages_through_entries(client, admin):
    for n in range(3):
        client.post("/gpus", json=make_gpu(model=f"RTX Page {n}"), headers=admin)
    page = client.get("/admin/audit?limit=2&offset=1", headers=admin).json()
    assert page["total"] == 3
    assert [e["gpu_model"] for e in page["entries"]] == ["RTX Page 1", "RTX Page 0"]


def test_a_logging_failure_never_blocks_the_change(client, admin, monkeypatch):
    def broken(self, entry):
        raise database.DatabaseUnavailableError()
    monkeypatch.setattr(database.AuditRepository, "add", broken)
    response = client.post("/gpus", json=make_gpu(model="RTX Still Saved"), headers=admin)
    assert response.status_code == 201
