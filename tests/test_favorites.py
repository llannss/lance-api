"""Favorite GPUs saved to each account. Run with:  python -m pytest"""

import favorites
from conftest import ADMIN_EMAIL, ADMIN_PASSWORD, log_in


def test_favorites_start_empty(client):
    response = client.get("/me/favorites")
    assert response.status_code == 200
    assert response.json() == {"count": 0, "gpu_ids": [], "gpus": []}


def test_add_list_and_remove_favorites_newest_first(client):
    assert client.put("/me/favorites/2").status_code == 204
    assert client.put("/me/favorites/1").status_code == 204
    body = client.get("/me/favorites").json()
    assert body["gpu_ids"] == [1, 2]
    assert [g["model"] for g in body["gpus"]] == ["GeForce RTX 5090", "GeForce RTX 4090"]

    assert client.delete("/me/favorites/2").status_code == 204
    assert client.get("/me/favorites").json()["gpu_ids"] == [1]


def test_saving_twice_or_removing_a_missing_favorite_is_harmless(client, api):
    client.put("/me/favorites/1")
    assert client.put("/me/favorites/1").status_code == 204
    assert len(api.favorites) == 1
    assert client.delete("/me/favorites/3").status_code == 204


def test_favorite_of_a_missing_gpu_returns_404(client, api):
    assert client.put("/me/favorites/999").status_code == 404
    assert api.favorites == []


def test_favorites_are_private_to_each_account(anonymous, client, api):
    client.put("/me/favorites/1")
    admin = log_in(anonymous, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert anonymous.get("/me/favorites", headers=admin).json()["gpu_ids"] == []
    # The admin removing GPU 1 only touches the admin's own list.
    anonymous.delete("/me/favorites/1", headers=admin)
    assert client.get("/me/favorites").json()["gpu_ids"] == [1]


def test_favorites_need_a_login(anonymous, api):
    assert anonymous.get("/me/favorites").status_code == 401
    assert anonymous.put("/me/favorites/1").status_code == 401
    assert anonymous.delete("/me/favorites/1").status_code == 401
    assert api.favorites == []


def test_cookie_favorites_need_a_same_site_request(anonymous, api):
    anonymous.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert anonymous.put("/me/favorites/1").status_code == 403
    assert anonymous.put("/me/favorites/1", headers={"X-Requested-With": "fetch"}).status_code == 204


def test_deleted_gpus_drop_out_of_favorites(client, admin):
    client.put("/me/favorites/1")
    client.put("/me/favorites/2")
    client.delete("/gpus/2", headers=admin)
    assert client.get("/me/favorites").json()["gpu_ids"] == [1]


def test_there_is_a_limit_per_account(client, monkeypatch):
    monkeypatch.setattr(favorites, "MAX_FAVORITES", 2)
    client.put("/me/favorites/1")
    client.put("/me/favorites/2")
    third = client.put("/me/favorites/3")
    assert third.status_code == 409
    assert client.put("/me/favorites/1").status_code == 204   # re-saving still fine
