"""Register two local synthetic manifests using the Claude fixture catalog."""
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.core.config import Settings
from backend.app.models.database import Order, OrderItem, audit, connect_database


MANIFESTS = {
    "META-001": {"BLUE-BOX": 2, "RED-CAN": 1, "YELLOW-POUCH": 1},
    "META-002": {"BLUE-BOX": 3, "RED-CAN": 2, "YELLOW-POUCH": 2},
}


def register(db):
    source = db.scalar(select(Order).where(Order.reference == "CLAUDE-MISSING-001"))
    if source is None or source.data_source != "synthetic_claude":
        raise ValueError("CLAUDE-MISSING-001 synthetic source order is unavailable")
    products = {item.product.sku: item.product for item in source.items}
    if set(products) != {"BLUE-BOX", "RED-CAN", "YELLOW-POUCH"}:
        raise ValueError("Source order product catalog differs from expected SKUs")
    if any(product.reference_provenance != "SYNTHETIC" or not product.registered_reference_path
           for product in products.values()):
        raise ValueError("Source products need registered synthetic reference images")
    if {item.product.sku: item.quantity for item in source.items} != MANIFESTS["META-001"]:
        raise ValueError("Source order quantities differ from META-001 manifest")

    created = 0
    for reference, items in MANIFESTS.items():
        order_id = f"meta-order-{reference.lower()}"
        existing = db.scalar(select(Order).where(Order.reference == reference))
        if existing:
            if (existing.id != order_id or existing.data_source != "synthetic_claude"
                    or {item.product.sku: item.quantity for item in existing.items} != items):
                raise ValueError(f"Existing {reference} conflicts with requested manifest")
            continue
        if db.get(Order, order_id):
            raise ValueError(f"Order ID for {reference} is already in use")
        order = Order(id=order_id, reference=reference, customer="Synthetic demonstration",
                      preparation_status="READY_FOR_INSPECTION", data_source="synthetic_claude")
        db.add(order)
        db.flush()
        for index, (sku, quantity) in enumerate(items.items()):
            db.add(OrderItem(id=f"{order_id}-item-{index}", order_id=order_id,
                             product_id=products[sku].id, quantity=quantity))
        audit(db, "SYNTHETIC_ORDER_REGISTERED", order_id,
              {"source_order_id": source.id, "provenance": "SYNTHETIC",
               "manifest": items, "inspection_created": False})
        created += 1
    db.commit()
    return created


if __name__ == "__main__":
    engine, sessions = connect_database(Settings.from_env().database_url)
    try:
        with sessions() as db:
            count = register(db)
        print(f"Registered {count} new synthetic orders; no inspections created")
    finally:
        engine.dispose()
