"""Conservative local image checks. These measurements cannot establish object visibility."""
from __future__ import annotations

import io
from PIL import Image, ImageFilter, ImageOps, ImageStat


GUIDANCE = {
    "LOW_RESOLUTION": "Move the camera closer and capture the entire packing surface.",
    "LOW_LIGHT": "Improve lighting and retake the photo.",
    "OVEREXPOSED": "Reduce direct light and retake the photo.",
    "EXCESSIVE_BLUR": "Keep the camera steady and retake the photo.",
    "POTENTIAL_GLARE": "Change the camera angle to avoid reflective glare.",
}


def analyze_image_quality(content: bytes, *, min_side: int = 256) -> dict:
    try:
        with Image.open(io.BytesIO(content)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.load()
    except Exception:
        return {"quality_status": "TECHNICAL_FAILURE", "issues": ["INVALID_IMAGE"],
                "retake_instructions": ["Upload a valid PNG, JPEG, or WEBP image."], "measurements": {}}
    gray = image.convert("L")
    gray.thumbnail((512, 512))
    pixels = list(gray.get_flattened_data())
    mean = ImageStat.Stat(gray).mean[0]
    dark_fraction = sum(value < 30 for value in pixels) / len(pixels)
    clipped_fraction = sum(value > 248 for value in pixels) / len(pixels)
    # Laplacian variance is a warning only: a plain package may legitimately have little texture.
    laplacian = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=128)
    edge_variance = ImageStat.Stat(gray.filter(laplacian)).var[0]
    issues = []
    if min(image.size) < min_side:
        issues.append("LOW_RESOLUTION")
    if mean < 40 and dark_fraction > 0.7:
        issues.append("LOW_LIGHT")
    if mean > 245 and clipped_fraction > 0.85:
        issues.append("OVEREXPOSED")
    # Local saturation can be a reflection or a white label; ask for review rather than rejecting.
    if 0.03 < clipped_fraction < 0.85 and mean > 210:
        issues.append("POTENTIAL_GLARE")
    if edge_variance < 2 and 40 <= mean <= 245:
        issues.append("EXCESSIVE_BLUR")
    decisive = {"LOW_RESOLUTION", "LOW_LIGHT", "OVEREXPOSED"}
    status = ("RETAKE_RECOMMENDED" if decisive.intersection(issues) else
              "NEEDS_HUMAN_REVIEW" if issues else "ACCEPTABLE")
    return {"quality_status": status, "issues": issues,
            "retake_instructions": [GUIDANCE[issue] for issue in issues],
            "measurements": {"width": image.width, "height": image.height,
                             "mean_luminance": round(mean, 1),
                             "dark_fraction": round(dark_fraction, 3),
                             "clipped_fraction": round(clipped_fraction, 3),
                             "edge_variance": round(edge_variance, 1)}}
