"""Checks and converts uploaded GPU pictures.

Every upload is opened with Pillow and saved again as a new WebP file, so:
- a file that only claims to be an image (wrong extension or Content-Type)
  is rejected, because Pillow cannot open it;
- anything hidden inside the original (camera GPS data, extra bytes, a
  script disguised as an image) is left behind;
- every picture ends up the same format and a sensible size.
"""

import io
import warnings

from PIL import Image, ImageOps

# Vercel refuses request bodies over 4.5 MB, so stay below that.
MAX_UPLOAD_BYTES = 4 * 1024 * 1024
# Refuse "decompression bombs": tiny files that expand to huge images.
MAX_PIXELS = 40_000_000
MAX_SIDE = 1000             # longest side after resizing, in pixels
WEBP_QUALITY = 85
ACCEPTED_FORMATS = {"PNG", "JPEG", "WEBP"}

Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class InvalidImageError(Exception):
    """The upload is not a PNG, JPEG or WebP picture Pillow can read."""


class ImageTooLargeError(Exception):
    """The upload is bigger than MAX_UPLOAD_BYTES."""


def to_webp(data: bytes, max_bytes: int = MAX_UPLOAD_BYTES, max_side: int = MAX_SIDE, effort: int = 6) -> bytes:
    """Return a cleaned, resized WebP version of an uploaded picture.

    max_bytes only differs for local scripts; web uploads keep the 4 MB cap.
    max_side is larger for Marketplace photos, where detail matters.
    effort is WebP's speed/size trade-off (0 fast .. 6 smallest); sellers
    upload several photos at once, so the Marketplace uses a faster setting.
    """
    if len(data) > max_bytes:
        raise ImageTooLargeError()
    if not data:
        raise InvalidImageError()

    try:
        with warnings.catch_warnings():
            # Pillow only *warns* between 1x and 2x MAX_IMAGE_PIXELS; refuse those too.
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as probe:
                if probe.format not in ACCEPTED_FORMATS:
                    raise InvalidImageError()
                probe.verify()                      # structural check of the file
            with Image.open(io.BytesIO(data)) as img:   # verify() needs a fresh open
                img = ImageOps.exif_transpose(img)  # respect phone rotation, then drop EXIF
                img.thumbnail((max_side, max_side))
                has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
                img = img.convert("RGBA" if has_alpha else "RGB")
                out = io.BytesIO()
                img.save(out, "WEBP", quality=WEBP_QUALITY, method=effort)
                return out.getvalue()
    except InvalidImageError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise InvalidImageError() from error
    except Exception as error:   # Pillow raises many kinds of errors for bad files
        raise InvalidImageError() from error
