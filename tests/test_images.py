"""GPU pictures in Supabase Storage. Run with:  python -m pytest"""

import io

from PIL import Image

import images
from conftest import make_gpu

BUCKET_URL = "https://test-project.supabase.co/storage/v1/object/public/gpu-images/"


def picture(fmt="PNG", size=(1600, 900), mode="RGB") -> bytes:
    out = io.BytesIO()
    color = (8, 116, 249, 128) if mode == "RGBA" else (8, 116, 249)  # half-transparent for RGBA
    Image.new(mode, size, color if mode != "P" else 1).save(out, fmt)
    return out.getvalue()


def upload(client, admin, gpu_id=1, data=None, name="card.png", content_type="image/png"):
    data = picture() if data is None else data
    return client.post(f"/gpus/{gpu_id}/image", headers=admin, files={"file": (name, data, content_type)})


def test_admin_upload_stores_a_resized_webp_and_sets_image_url(client, admin, api):
    response = upload(client, admin)
    assert response.status_code == 200, response.text
    url = response.json()["image_url"]
    assert url.startswith(BUCKET_URL + "gpu-1-") and url.endswith(".webp")

    name = url.removeprefix(BUCKET_URL)
    stored = Image.open(io.BytesIO(api.files[name]))
    assert stored.format == "WEBP"
    assert max(stored.size) == images.MAX_SIDE          # 1600x900 shrunk to 1000x562
    assert client.get("/gpus/1").json()["image_url"] == url


def test_replacing_a_picture_deletes_the_old_file(client, admin, api):
    first = upload(client, admin).json()["image_url"]
    second = upload(client, admin).json()["image_url"]
    assert first != second
    assert list(api.files) == [second.removeprefix(BUCKET_URL)]


def test_delete_image_clears_the_url_and_the_file(client, admin, api):
    upload(client, admin)
    response = client.delete("/gpus/1/image", headers=admin)
    assert response.status_code == 200
    assert response.json()["image_url"] is None
    assert api.files == {}


def test_deleting_a_gpu_also_deletes_its_picture(client, admin, api):
    upload(client, admin)
    assert client.delete("/gpus/1", headers=admin).status_code == 204
    assert api.files == {}


def test_updating_gpu_details_keeps_the_picture(client, admin):
    url = upload(client, admin).json()["image_url"]
    client.put("/gpus/1", json=make_gpu(model="GeForce RTX 5090", description="New text."), headers=admin)
    assert client.get("/gpus/1").json()["image_url"] == url


def test_regular_users_and_visitors_cannot_upload(client, anonymous, api):
    files = {"file": ("card.png", picture(), "image/png")}
    assert client.post("/gpus/1/image", files=files).status_code == 403
    client.headers.pop("Authorization")
    assert client.post("/gpus/1/image", files=files).status_code == 401
    assert client.delete("/gpus/1/image").status_code == 401
    assert api.files == {}


def test_fake_and_unsupported_files_are_rejected(client, admin, api):
    fake = b"<script>alert(1)</script>" + b"x" * 200
    for data, name, ctype in (
        (fake, "evil.png", "image/png"),                     # claims PNG, isn't
        (picture("GIF", mode="P"), "anim.gif", "image/gif"),  # real image, not accepted
        (picture("BMP", size=(200, 100)), "old.bmp", "image/bmp"),
        (b"", "empty.png", "image/png"),
    ):
        response = upload(client, admin, data=data, name=name, content_type=ctype)
        assert response.status_code == 422, name
        assert response.json() == {"detail": "Upload a PNG, JPEG or WebP picture."}
    assert api.files == {}


def test_files_over_4_mb_are_rejected(client, admin, api):
    big = b"\x89PNG" + b"0" * (images.MAX_UPLOAD_BYTES + 10)
    response = upload(client, admin, data=big)
    assert response.status_code == 413
    assert api.files == {}


def test_decompression_bombs_are_rejected(client, admin, api, monkeypatch):
    monkeypatch.setattr(images.Image, "MAX_IMAGE_PIXELS", 1000)
    response = upload(client, admin, data=picture(size=(2000, 2000)))
    assert response.status_code == 422
    assert api.files == {}


def test_transparency_is_kept_and_jpeg_is_accepted(client, admin, api):
    png = upload(client, admin, data=picture(mode="RGBA", size=(300, 200)))
    name = png.json()["image_url"].removeprefix(BUCKET_URL)
    assert Image.open(io.BytesIO(api.files[name])).mode == "RGBA"
    jpeg = upload(client, admin, gpu_id=2, data=picture("JPEG"), name="c.jpg", content_type="image/jpeg")
    assert jpeg.status_code == 200


def test_upload_for_a_missing_gpu_returns_404(client, admin, api):
    assert upload(client, admin, gpu_id=999).status_code == 404
    assert client.delete("/gpus/999/image", headers=admin).status_code == 404
    assert api.files == {}


def test_storage_failure_returns_503_and_leaves_the_gpu_unchanged(client, admin, api):
    api.storage_failure = True
    response = upload(client, admin)
    assert response.status_code == 503
    assert "boom" not in response.text
    assert client.get("/gpus/1").json()["image_url"] is None


def test_only_files_in_our_bucket_are_ever_deleted():
    path = images and __import__("database").ImageStore.path_from_url
    assert path(BUCKET_URL + "gpu-1-abc.webp") == "gpu-1-abc.webp"
    assert path(BUCKET_URL + "gpu-1-abc.webp?v=2") == "gpu-1-abc.webp"
    for other in (None, "", "https://evil.example/x.webp", BUCKET_URL + "../users/x", BUCKET_URL + "a/b.webp", BUCKET_URL):
        assert path(other) is None
