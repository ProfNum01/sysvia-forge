"""Validate owner-supplied physical product data before explicit local registration."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from PIL import Image
from sqlalchemy import select

from backend.app.models.database import Inventory, Order, OrderItem, Product, audit


SKU = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,63}$")


def _image(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("A relative image path is required")
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Image path is missing or leaves the dataset")
    if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("Unsupported image format")
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        if min(image.size) < 256 or image.width * image.height > 20_000_000:
            raise ValueError("Image resolution is outside supported limits")
    if path.stat().st_size > 15 * 1024 * 1024:
        raise ValueError("Image exceeds upload limit")
    return path


def validate_physical_manifest(path: Path) -> dict:
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    root = path.parent
    if (data.get("provenance") != "PHYSICAL_CAPTURE" or data.get("rights_confirmed") is not True
            or not isinstance(data.get("dataset_id"), str) or not data["dataset_id"].strip()):
        raise ValueError("Owner-confirmed physical provenance and dataset ID are required")
    products = data.get("products")
    if not isinstance(products, list) or not 1 <= len(products) <= 50:
        raise ValueError("One to fifty registered products are required")
    seen = set()
    for product in products:
        sku = product.get("sku")
        if not isinstance(sku, str) or not SKU.fullmatch(sku) or sku in seen:
            raise ValueError("Product SKUs must be unique and explicit")
        seen.add(sku)
        if not isinstance(product.get("name"), str) or not product["name"].strip():
            raise ValueError("Product name is required")
        if product.get("visible_label") != sku:
            raise ValueError("Visible label registration must equal the SKU")
        barcode = product.get("barcode")
        if barcode is not None and (not isinstance(barcode, str) or not 1 <= len(barcode) <= 128):
            raise ValueError("Optional barcode must be a bounded string")
        if type(product.get("inventory_quantity")) is not int or product["inventory_quantity"] < 0:
            raise ValueError("Owner-provided inventory quantity is required")
        if not isinstance(product.get("inventory_location"), str) or not product["inventory_location"].strip():
            raise ValueError("Owner-provided inventory location is required")
        _image(root, product.get("reference_image"))
    before = _image(root, data.get("before_image"))
    if data.get("after_image"):
        after = _image(root, data["after_image"])
        if before == after or hashlib.sha256(before.read_bytes()).digest() == hashlib.sha256(after.read_bytes()).digest():
            raise ValueError("Before and after evidence must be distinct")
    order = data.get("order")
    if not isinstance(order, dict) or not isinstance(order.get("reference"), str) or not order["reference"].strip():
        raise ValueError("Physical order reference is required")
    items = order.get("items")
    if not isinstance(items, dict) or not items or any(sku not in seen or type(qty) is not int or qty < 1
                                                     for sku, qty in items.items()):
        raise ValueError("Order items must map registered SKUs to positive quantities")
    return data


def register_physical_manifest(db, manifest_path: Path, data_dir: Path) -> dict:
    data = validate_physical_manifest(manifest_path)
    root = Path(manifest_path).resolve().parent
    if db.scalar(select(Order.id).where(Order.reference == data["order"]["reference"])):
        raise ValueError("Order reference already exists; registration is not a reset")
    for product in data["products"]:
        if db.get(Product, f"physical-{product['sku'].lower()}") or db.scalar(select(Product.id).where(Product.sku == product["sku"])):
            raise ValueError("Registered product ID or SKU already exists")
    target_root = Path(data_dir).resolve() / "physical_references"
    target_root.mkdir(parents=True, exist_ok=True)
    ids = {}
    for product in data["products"]:
        source = _image(root, product["reference_image"])
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        destination = target_root / f"{digest}.png"
        if not destination.exists():
            with Image.open(source) as image:
                image.convert("RGB").save(destination, format="PNG")
        pid = f"physical-{product['sku'].lower()}"
        ids[product["sku"]] = pid
        db.add(Product(id=pid, sku=product["sku"], name=product["name"], color="",
                       description=f"Registered physical product; visible label {product['visible_label']}",
                       registered_reference_path=str(destination), reference_provenance="PHYSICAL_CAPTURE",
                       visible_label=product["visible_label"], barcode=product.get("barcode")))
        db.flush()
        db.add(Inventory(id=f"inventory-{pid}", product_id=pid,
                         quantity_available=product["inventory_quantity"], location=product["inventory_location"]))
    order = Order(id=f"physical-order-{hashlib.sha256(data['order']['reference'].encode()).hexdigest()[:16]}",
                  reference=data["order"]["reference"], customer="Owner physical capture",
                  preparation_status="READY_FOR_INSPECTION", data_source="physical_capture")
    db.add(order)
    db.flush()
    for index, (sku, quantity) in enumerate(data["order"]["items"].items()):
        db.add(OrderItem(id=f"{order.id}-item-{index}", order_id=order.id,
                         product_id=ids[sku], quantity=quantity))
    audit(db, "PHYSICAL_DATASET_REGISTERED", order.id,
          {"dataset_id": data["dataset_id"], "provenance": "PHYSICAL_CAPTURE",
           "before_sha256": hashlib.sha256(_image(root, data["before_image"]).read_bytes()).hexdigest(),
           "after_sha256": hashlib.sha256(_image(root, data["after_image"]).read_bytes()).hexdigest() if data.get("after_image") else None,
           "inspection_created": False})
    db.commit()
    return {"order_id": order.id, "products_registered": len(ids), "inspection_created": False}
