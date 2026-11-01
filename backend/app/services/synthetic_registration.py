"""Register a Claude-generated fixture without physical provenance claims."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image
from sqlalchemy import select

from backend.app.models.database import Inventory, Order, OrderItem, Product, audit
from backend.app.services.physical_registration import SKU, _image


def validate_synthetic_manifest(path: Path) -> dict:
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    if (data.get("provenance") != "SYNTHETIC" or data.get("generator") != "Claude AI"
            or data.get("rights_confirmed") is not True or not data.get("dataset_id")):
        raise ValueError("Claude synthetic provenance, rights, and dataset ID are required")
    products = data.get("products")
    if not isinstance(products, list) or len(products) != 4:
        raise ValueError("Four synthetic products are required")
    expected = {"BLUE-BOX", "RED-CAN", "YELLOW-POUCH", "GREEN-CUBE"}
    if {p.get("sku") for p in products} != expected:
        raise ValueError("Synthetic SKU mapping is incomplete")
    for product in products:
        sku = product["sku"]
        if (not SKU.fullmatch(sku) or product.get("visible_label") != sku
                or not isinstance(product.get("name"), str) or not product["name"].strip()
                or type(product.get("inventory_quantity")) is not int or product["inventory_quantity"] != 10
                or product.get("inventory_location") != "Synthetic test inventory"):
            raise ValueError("Synthetic label or test inventory is invalid")
        _image(path.parent, product.get("reference_image"))
    _image(path.parent, data.get("before_image"))
    if data.get("after_image"):
        before = _image(path.parent, data["before_image"])
        after = _image(path.parent, data["after_image"])
        if before == after or hashlib.sha256(before.read_bytes()).digest() == hashlib.sha256(after.read_bytes()).digest():
            raise ValueError("Before and after must differ")
    order = data.get("order")
    if (not isinstance(order, dict) or not isinstance(order.get("reference"), str)
            or not order["reference"].strip() or order.get("items") != {"BLUE-BOX": 2, "RED-CAN": 1, "YELLOW-POUCH": 1}):
        raise ValueError("Synthetic test order is invalid")
    return data


def register_synthetic_manifest(db, manifest_path: Path, data_dir: Path) -> dict:
    data = validate_synthetic_manifest(manifest_path)
    if db.scalar(select(Order.id).where(Order.reference == data["order"]["reference"])):
        raise ValueError("Synthetic order already exists")
    for product in data["products"]:
        if db.scalar(select(Product.id).where(Product.sku == product["sku"])):
            raise ValueError("SKU already exists")
    reference_root = Path(data_dir).resolve() / "synthetic_references"
    reference_root.mkdir(parents=True, exist_ok=True)
    ids = {}
    for product in data["products"]:
        source = _image(Path(manifest_path).resolve().parent, product["reference_image"])
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        destination = reference_root / f"{digest}.png"
        if not destination.exists():
            with Image.open(source) as image:
                image.convert("RGB").save(destination, format="PNG")
        sku = product["sku"]
        pid = f"claude-{sku.lower()}"
        ids[sku] = pid
        db.add(Product(id=pid, sku=sku, name=product["name"], color="",
                       description=f"Claude AI synthetic fixture; visible label {sku}",
                       registered_reference_path=str(destination), reference_provenance="SYNTHETIC",
                       visible_label=sku))
        db.flush()
        db.add(Inventory(id=f"inventory-{pid}", product_id=pid, quantity_available=10,
                         location="Synthetic test inventory"))
    order = Order(id=f"claude-order-{hashlib.sha256(data['order']['reference'].encode()).hexdigest()[:16]}",
                  reference=data["order"]["reference"], customer="Claude AI synthetic fixture",
                  preparation_status="READY_FOR_INSPECTION", data_source="synthetic_claude")
    db.add(order)
    db.flush()
    for index, (sku, quantity) in enumerate(data["order"]["items"].items()):
        db.add(OrderItem(id=f"{order.id}-item-{index}", order_id=order.id,
                         product_id=ids[sku], quantity=quantity))
    audit(db, "SYNTHETIC_DATASET_REGISTERED", order.id,
          {"dataset_id": data["dataset_id"], "provenance": "SYNTHETIC", "generator": "Claude AI",
           "before_sha256": hashlib.sha256(_image(Path(manifest_path).resolve().parent, data["before_image"]).read_bytes()).hexdigest(),
           "inspection_created": False})
    db.commit()
    return {"order_id": order.id, "products_registered": len(ids), "inspection_created": False}
