"""
Image validation and preprocessing for the Crop Doctor pipeline.

Kept deliberately separate from inference so a real trained model
(ONNX / TorchScript) can be swapped in without touching validation logic.
"""
import io

from PIL import Image, UnidentifiedImageError

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_DIMENSION = 4096
TARGET_SIZE = (224, 224)


class ImageValidationError(Exception):
    pass


def validate_and_load(image_bytes: bytes, content_type: str, max_size_mb: int) -> Image.Image:
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ImageValidationError(f"Unsupported image type '{content_type}'. Allowed: JPEG, PNG, WEBP.")
    if len(image_bytes) > max_size_mb * 1024 * 1024:
        raise ImageValidationError(f"Image exceeds the {max_size_mb}MB upload limit.")
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.verify()
        img = Image.open(io.BytesIO(image_bytes))  # re-open: verify() invalidates the file handle
        img.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageValidationError("The uploaded file is not a valid image.") from exc

    if img.width > MAX_DIMENSION or img.height > MAX_DIMENSION:
        raise ImageValidationError("Image dimensions are too large.")

    return img.convert("RGB")


def resize_for_model(img: Image.Image) -> Image.Image:
    return img.resize(TARGET_SIZE)
