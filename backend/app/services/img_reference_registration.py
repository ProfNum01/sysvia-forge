"""Install reviewed synthetic v2 references for the four IMG catalog products."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from PIL import Image
from sqlalchemy import select

from backend.app.models.database import Product, audit


COLORS = ("yellow", "green", "blue", "red")


def install_img_references(db, data_dir: Path, source_dir: Path) -> int:
    source_dir = Path(source_dir).resolve()
    target_dir = (Path(data_dir).resolve() / "references")
    products = {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(
        [f"img-{color}-box" for color in COLORS])))}
    if len(products) != 4:
        raise ValueError("All four IMG catalog products must already be registered")
    prepared = []
    for color in COLORS:
        product_id = f"img-{color}-box"
        product = products[product_id]
        if product.sku != f"IMG-{color.upper()}-BOX" or product.visible_label != "NONE" or product.reference_provenance != "SYNTHETIC":
            raise ValueError("IMG catalog registration does not match the synthetic data")
        source = source_dir / f"{product_id}-v2.png"
        if not source.is_file() or source.stat().st_size > 15 * 1024 * 1024:
            raise ValueError("Versioned reference image is missing or oversized")
        with Image.open(source) as image:
            image.verify()
        with Image.open(source) as image:
            if image.format != "PNG" or min(image.size) < 256 or image.width * image.height > 20_000_000:
                raise ValueError("Versioned reference image has unsupported dimensions")
        destination = target_dir / source.name
        if destination.exists() and hashlib.sha256(destination.read_bytes()).digest() != hashlib.sha256(source.read_bytes()).digest():
            raise ValueError("A different versioned reference already exists")
        already = Path(product.registered_reference_path or "").name == source.name
        prepared.append((product, source, destination, already, color))
    target_dir.mkdir(parents=True, exist_ok=True)
    changed = 0
    for product, source, destination, already, color in prepared:
        if not destination.exists():
            shutil.copyfile(source, destination)
        if already:
            continue
        previous = Path(product.registered_reference_path or "").name
        product.registered_reference_path = str(destination)
        product.description = (f"Unbranded solid {color} cube-shaped box with three visible faces; "
                               "no visible sku label; synthetic generated reference, not scene evidence")
        audit(db, "SYNTHETIC_REFERENCE_UPDATED", product.id,
              {"previous_filename": previous, "new_filename": destination.name,
               "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
               "provenance": "SYNTHETIC_IMAGEGEN", "inspection_updated": False})
        changed += 1
    db.commit()
    return changed
