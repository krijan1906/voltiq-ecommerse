"""Reusable validators for uploads and business input."""
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
MAX_IMAGE_DIMENSION = 6000


def validate_image_upload(file):
    """Validate extension, real image content, dimensions and file size."""
    if not file:
        return
    name = getattr(file, "name", "")
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError("Unsupported image type. Use JPG, PNG, WEBP or GIF.")

    max_bytes = getattr(settings, "MAX_UPLOAD_SIZE_MB", 5) * 1024 * 1024
    size = getattr(file, "size", 0)
    if size and size > max_bytes:
        raise ValidationError(f"Image must be smaller than {getattr(settings, 'MAX_UPLOAD_SIZE_MB', 5)} MB.")

    try:
        file.seek(0)
        image = Image.open(file)
        image.verify()
        fmt = (image.format or "").upper()
        if fmt not in ALLOWED_IMAGE_FORMATS:
            raise ValidationError("The uploaded file is not a valid image.")
        file.seek(0)
        probe = Image.open(file)
        if max(probe.size) > MAX_IMAGE_DIMENSION:
            raise ValidationError("Image dimensions are too large (max 6000px).")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError("The uploaded file is not a valid image.") from exc
    finally:
        try:
            file.seek(0)
        except Exception:
            pass
