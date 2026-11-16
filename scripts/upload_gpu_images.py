"""One-time move of the website's GPU pictures into Supabase Storage.

For every GPU in public.gpus that has no picture yet, this finds the matching
file in the website's images folder (same naming rule the website uses:
"GeForce RTX 4090" -> rtx-4090.png), converts it to WebP exactly like the
upload route does, stores it in the gpu-images bucket and sets image_url.

Run from the lance-api folder, with the real SUPABASE_URL and
SUPABASE_SECRET_KEY in .env, after running supabase/storage.sql:

    python scripts/upload_gpu_images.py ../lance-api-gpu-finder-main/images --dry-run
    python scripts/upload_gpu_images.py ../lance-api-gpu-finder-main/images

Use --replace to also replace pictures that are already set.
"""

import argparse
import re
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import images  # noqa: E402
from database import GPURepository, ImageStore, _get_client  # noqa: E402


def slug(model: str) -> str:
    """Mirror of getImageFile() in the website's js/script.js."""
    short = re.sub(r"^(GeForce|Radeon|Intel)\s+", "", model or "gpu", flags=re.I).lower()
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", short))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path, help="the website's images folder")
    parser.add_argument("--dry-run", action="store_true", help="only report what would happen")
    parser.add_argument("--replace", action="store_true", help="also replace existing pictures")
    args = parser.parse_args()

    if not args.folder.is_dir():
        print(f"Not a folder: {args.folder}")
        return 1

    client = _get_client()
    gpus = GPURepository(client)
    store = ImageStore(client)

    done, skipped, missing, failed = 0, 0, [], []
    for gpu in gpus.list_all():
        label = f"#{gpu['id']} {gpu['model']}"
        if gpu.get("image_url") and not args.replace:
            skipped += 1
            continue
        source = args.folder / f"{slug(gpu['model'])}.png"
        if not source.is_file():
            missing.append(label)
            continue
        try:
            # Local files aren't limited by Vercel's upload cap.
            webp = images.to_webp(source.read_bytes(), max_bytes=20 * 1024 * 1024)
        except (images.InvalidImageError, images.ImageTooLargeError) as error:
            failed.append(f"{label}: {type(error).__name__}")
            continue
        size_kb = len(webp) // 1024
        if args.dry_run:
            print(f"would upload {source.name:28} -> {label}  ({size_kb} KB WebP)")
            done += 1
            continue
        url = store.upload(f"gpu-{gpu['id']}-{secrets.token_hex(8)}.webp", webp)
        gpus.set_image_url(gpu["id"], url)
        store.remove_url(gpu.get("image_url"))
        print(f"uploaded {source.name:28} -> {label}  ({size_kb} KB)")
        done += 1

    verb = "would upload" if args.dry_run else "uploaded"
    print(f"\n{verb}: {done}   already had a picture: {skipped}   no file found: {len(missing)}   failed: {len(failed)}")
    for line in missing:
        print(f"  no file: {line}")
    for line in failed:
        print(f"  failed:  {line}")
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
