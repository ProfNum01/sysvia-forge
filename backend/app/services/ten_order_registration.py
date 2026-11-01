"""Register the ten synthetic order manifests without creating inspections."""
import hashlib
import json
from pathlib import Path

from sqlalchemy import select

from backend.app.models.database import Order, OrderItem, Product, audit
from backend.app.services.physical_registration import _image


def register_ten_orders(db, manifest_path: Path) -> int:
    path = Path(manifest_path).resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    root = path.parents[3]
    if data.get("dataset_id") != "ten-synthetic-whole-orders-v1" or data.get("provenance") != "SYNTHETIC":
        raise ValueError("Unexpected synthetic dataset")
    cases = data.get("cases")
    if not isinstance(cases, list) or len(cases) != 10:
        raise ValueError("Ten cases are required")
    if len({c.get("order_id") for c in cases}) != 10:
        raise ValueError("Order references must be unique")
    products = {p.sku: p for p in db.scalars(select(Product).where(Product.sku.in_(data["catalog"].keys())))}
    if set(products) != {"BLUE-BOX", "RED-CAN", "YELLOW-POUCH", "GREEN-CUBE"} or any(
        p.reference_provenance != "SYNTHETIC" for p in products.values()
    ):
        raise ValueError("The four registered synthetic products are required")
    prepared = []
    for case in cases:
        reference = case["order_id"]
        if not isinstance(reference, str) or not reference.startswith("TEN-ORDER-"):
            raise ValueError("Unexpected order reference")
        order_path = path.parent / "orders" / f"{reference}.json"
        order_data = json.loads(order_path.read_text(encoding="utf-8"))
        items = case["expected_quantities"]
        if (order_data.get("reference") != reference or order_data.get("items") != items
                or order_data.get("image") != case.get("evidence") or not isinstance(items, dict)
                or not items or any(s not in products or type(q) is not int or q < 1 for s, q in items.items())):
            raise ValueError("Order manifest does not match dataset")
        evidence = case["evidence"]
        if not isinstance(evidence, str) or not evidence.startswith("evaluation/datasets/ten-orders/images/"):
            raise ValueError("Evidence must be a ten-order image")
        image = _image(root, evidence)
        existing = db.scalar(select(Order).where(Order.reference == reference))
        if existing:
            if existing.data_source != "synthetic_claude" or {i.product.sku: i.quantity for i in existing.items} != items:
                raise ValueError("Existing order conflicts with synthetic manifest")
            continue
        prepared.append((reference, items, hashlib.sha256(image.read_bytes()).hexdigest()))
    for reference, items, image_hash in prepared:
        order_id = f"ten-order-{reference.rsplit('-', 1)[-1]}"
        if db.get(Order, order_id):
            raise ValueError("Order ID already exists")
        order = Order(id=order_id, reference=reference, customer="Synthetic demonstration",
                      preparation_status="READY_FOR_INSPECTION", data_source="synthetic_claude")
        db.add(order)
        db.flush()
        for index, (sku, quantity) in enumerate(items.items()):
            db.add(OrderItem(id=f"{order_id}-item-{index}", order_id=order_id,
                             product_id=products[sku].id, quantity=quantity))
        audit(db, "SYNTHETIC_ORDER_REGISTERED", order_id,
              {"dataset_id": data["dataset_id"], "provenance": "SYNTHETIC",
               "image_sha256": image_hash, "inspection_created": False})
    db.commit()
    return len(prepared)
