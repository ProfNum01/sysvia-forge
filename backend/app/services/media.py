from __future__ import annotations

import hashlib
import io
import warnings
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from PIL import Image, ImageOps


def prepare_image(upload, settings):
    if upload.content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(422, "Upload a PNG, JPEG, or WEBP image.")
    content = upload.file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(413, "Image exceeds the 15 MiB upload limit.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as candidate:
                if candidate.format not in {"PNG", "JPEG", "WEBP"} or candidate.width*candidate.height > 20_000_000:
                    raise ValueError("unsupported image")
                image = ImageOps.exif_transpose(candidate).convert("RGB")
                image.load()
            output = io.BytesIO()
            image.save(output, "PNG")
            normalized = output.getvalue()
            if len(normalized) > settings.max_upload_bytes:
                raise ValueError("normalized image exceeds inline provider limit")
    except Exception:
        raise HTTPException(422, "Image is invalid, unsupported, or exceeds 20 megapixels.") from None
    digest = hashlib.sha256(normalized).hexdigest()
    photo_id = str(uuid4())
    destination = settings.data_dir / "uploads" / f"{photo_id}.png"
    return photo_id, digest, destination, normalized, image.width, image.height
