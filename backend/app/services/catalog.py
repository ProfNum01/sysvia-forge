"""Explicit SKU mappings for original synthetic references, not warehouse identity claims."""
from pathlib import Path, PureWindowsPath
import re
from PIL import Image, ImageDraw, ImageFont

REFERENCE_CATALOG = {
    "product-red": {"sku": "PS-RED-01", "color": "#d83238", "shape": "canister"},
    "product-blue": {"sku": "PS-BLUE-02", "color": "#215fcc", "shape": "box"},
    "product-amber": {"sku": "PS-AMBER-03", "color": "#bf7f21", "shape": "bottle"},
    "product-green": {"sku": "PS-GREEN-04", "color": "#238355", "shape": "pouch"},
    # Image-manifest box products — reference images cropped from real photo
    "img-yellow-box": {"sku": "IMG-YELLOW-BOX", "color": "#f5c518", "shape": "box", "no_sku_label": True},
    "img-red-box":    {"sku": "IMG-RED-BOX",    "color": "#e63232", "shape": "box", "no_sku_label": True},
    "img-blue-box":   {"sku": "IMG-BLUE-BOX",   "color": "#2563eb", "shape": "box", "no_sku_label": True},
    "img-green-box":  {"sku": "IMG-GREEN-BOX",  "color": "#16a34a", "shape": "box", "no_sku_label": True},
}


def reference_path(data_dir, product_id, sku, registered_reference_path=None):
    if registered_reference_path:
        candidate = Path(registered_reference_path).resolve()
        roots = (
            (Path(data_dir) / "physical_references").resolve(),
            (Path(data_dir) / "synthetic_references").resolve(),
            # Allow references/ for catalog-registered real-photo crops
            (Path(data_dir) / "references").resolve(),
            (Path(data_dir) / "user_references").resolve(),
        )
        if any(candidate.is_relative_to(root) for root in roots) and candidate.is_file():
            return candidate
        # The local SQLite database is shared by Windows and Docker. Resolve
        # only a known catalog filename or a content-addressed reference from
        # a Windows /data subdirectory into the container's mounted data root.
        windows = PureWindowsPath(registered_reference_path)
        parts = windows.parts
        if len(parts) >= 3 and parts[-3].lower() == "data":
            folder, filename = parts[-2], parts[-1]
            if folder == "references":
                known = REFERENCE_CATALOG.get(product_id)
                allowed = known is not None and known["sku"] == sku and filename in {
                    f"{product_id}.png", f"{product_id}-v2.png"}
            else:
                allowed = folder in {"physical_references", "synthetic_references", "user_references"} and bool(
                    re.fullmatch(r"[0-9a-f]{64}\.png", filename))
            if allowed:
                mapped = (Path(data_dir) / folder / filename).resolve()
                if mapped.is_relative_to((Path(data_dir) / folder).resolve()) and mapped.is_file():
                    return mapped
        return None
    item = REFERENCE_CATALOG.get(product_id)
    if not item or item["sku"] != sku:
        return None
    return Path(data_dir) / "references" / f"{product_id}.png"


def ensure_catalog_references(data_dir):
    """Create only missing reference assets. Never overwrite owner files or inspection evidence."""
    folder = Path(data_dir) / "references"
    folder.mkdir(parents=True, exist_ok=True)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 27)
        small = ImageFont.truetype("DejaVuSans.ttf", 14)
    except OSError:
        font = ImageFont.load_default(size=27)
        small = ImageFont.load_default(size=14)
    for pid, item in REFERENCE_CATALOG.items():
        path = reference_path(data_dir, pid, item["sku"])
        if path.exists():
            continue
        image = Image.new("RGB", (520, 520), "#edf0f5")
        draw = ImageDraw.Draw(image)
        draw.text((20, 18), "ORIGINAL SYNTHETIC REFERENCE", fill="#172335", font=small)
        shape, color = item["shape"], item["color"]
        if shape == "canister":
            draw.rounded_rectangle((125, 110, 395, 440), radius=22, fill=color)
            draw.rectangle((200, 80, 315, 115), fill="#9b1c24")
        elif shape == "box":
            draw.rectangle((95, 160, 395, 440), fill=color)
            draw.polygon([(95,160),(145,110),(445,110),(395,160)], fill="#5e8feb")
            draw.polygon([(395,160),(445,110),(445,390),(395,440)], fill="#153e92")
        elif shape == "bottle":
            draw.rounded_rectangle((155, 185, 365, 450), radius=44, fill=color)
            draw.rectangle((215, 100, 305, 205), fill=color)
            draw.rectangle((210, 80, 310, 115), fill="#563e1a")
        else:
            draw.polygon([(130,110),(390,110),(410,440),(110,440)], fill=color)
            draw.rectangle((130,110,390,137), fill="#145d3b")
        draw.rectangle((110, 265, 410, 340), fill="white")
        bbox = draw.textbbox((0,0), item["sku"], font=font)
        draw.text(((520-bbox[2])/2, 288), item["sku"], font=font, fill="#111111")
        draw.text((20, 480), "Explicit SKU mapping; a reference is not scene evidence.", font=small, fill="#344054")
        image.save(path, "PNG")
