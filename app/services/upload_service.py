import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import settings
from app.exceptions import FileTooLargeError, UnsupportedFileTypeError

ALLOWED = {
    "image/jpeg": (".jpg", ".jpeg"),
    "image/png": (".png",),
    "image/webp": (".webp",),
}
CHUNK = 64 * 1024


def _matches_signature(head: bytes, content_type: str) -> bool:
    """Check real file bytes (magic numbers) so a renamed .exe cannot pass as .png."""
    if content_type == "image/jpeg":
        return head.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    return False


def save_product_image(file: UploadFile, old_path: str | None = None) -> str:
    content_type = file.content_type or ""
    ext = Path(file.filename or "").suffix.lower()
    if content_type not in ALLOWED or ext not in ALLOWED[content_type]:
        raise UnsupportedFileTypeError("Only JPEG, PNG and WEBP images are allowed (.jpg, .jpeg, .png, .webp)")

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    data = bytearray()
    while chunk := file.file.read(CHUNK):
        data.extend(chunk)
        if len(data) > max_bytes:
            raise FileTooLargeError(f"File too large. Maximum size is {settings.MAX_UPLOAD_SIZE_MB} MB")
    if not data:
        raise UnsupportedFileTypeError("Uploaded file is empty")
    if not _matches_signature(bytes(data[:12]), content_type):
        raise UnsupportedFileTypeError("File content does not match its declared image type")

    folder = Path(settings.UPLOAD_DIR) / "products"
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"  # never trust the client's filename
    (folder / filename).write_bytes(data)

    if old_path:
        (Path(settings.UPLOAD_DIR) / old_path).unlink(missing_ok=True)
    return f"products/{filename}"
