from sqlalchemy import select
from backend.app.models.database import Inventory, Order, OrderItem, Product, audit


def seed_demo(db):
    """Explicit, idempotent synthetic order seed. Never creates inspection evidence."""
    if db.scalar(select(Order.id).limit(1)):
        return False
    products = [
        ("product-red", "PS-RED-01", "Red utility canister", "#ef6464", "a red rectangular canister"),
        ("product-blue", "PS-BLUE-02", "Blue supply box", "#6d9bf1", "a blue cardboard box"),
        ("product-amber", "PS-AMBER-03", "Amber sample bottle", "#e8b35b", "an amber glass bottle"),
        ("product-green", "PS-GREEN-04", "Green sealed pouch", "#67b99a", "a green sealed pouch"),
    ]
    for index, (pid, sku, name, color, description) in enumerate(products):
        db.add(Product(id=pid, sku=sku, name=name, color=color, description=description))
    db.flush()
    for index, (pid, *_rest) in enumerate(products):
        db.add(Inventory(id=f"inventory-{index+1}", product_id=pid, quantity_available=20+index*8,
                         location=f"Demo rack {chr(65+index)}-01"))
    quantities = [[("product-red", 2), ("product-blue", 1)],
                  [("product-amber", 3), ("product-green", 2)],
                  [("product-blue", 2), ("product-green", 1)],
                  [("product-red", 1), ("product-amber", 2)],
                  [("product-red", 1), ("product-blue", 1), ("product-amber", 1), ("product-green", 1)]]
    for index, lines in enumerate(quantities, 1001):
        order = Order(id=f"order-{index}", reference=f"PS-{index}", customer=f"Synthetic · Station {index-1000:02}",
                      preparation_status="PREPARING" if index == 1004 else "READY_FOR_INSPECTION")
        db.add(order)
        db.flush()
        for line, (pid, qty) in enumerate(lines, 1):
            db.add(OrderItem(id=f"item-{index}-{line}", order_id=order.id, product_id=pid, quantity=qty))
    audit(db, "DEMO_DATA_SEEDED", "demo", {"orders": 5, "products": 4, "source": "synthetic_seed"})
    db.commit()
    return True


def seed_packing_demo(db):
    """Add an isolated shape catalog and two orders; never alter existing orders."""
    if db.get(Order, "order-packing-missing") or db.get(Order, "order-packing-extra"):
        return False
    products = [
        ("packing-blue-box", "PACK-BLUE-BOX", "Blue rectangular box", "#1269af", "blue rectangular box; no visible SKU label"),
        ("packing-red-can", "PACK-RED-CAN", "Red cylindrical can", "#aa2525", "red cylinder; no visible SKU label"),
        ("packing-yellow-pouch", "PACK-YELLOW-POUCH", "Yellow pouch", "#e8bd20", "yellow pouch; no visible SKU label"),
        ("packing-green-cube", "PACK-GREEN-CUBE", "Green cube box", "#227246", "green cube-shaped box; no visible SKU label"),
    ]
    for index, (pid, sku, name, color, description) in enumerate(products):
        if not db.get(Product, pid):
            p = Product(id=pid, sku=sku, name=name, color=color, description=description)
            # Mark that no visible SKU label is present so reconciliation uses
            # visual-candidate matching instead of requiring label_text == SKU.
            p.visible_label = "NONE"
            db.add(p)
            db.flush()
            db.add(Inventory(id=f"inventory-packing-{index}", product_id=pid,
                             quantity_available=20, location="Synthetic packing rack"))
    db.flush()
    for suffix in ("missing", "extra"):
        order = Order(id=f"order-packing-{suffix}", reference=f"PACK-{suffix.upper()}",
                      customer="Synthetic packing scene", preparation_status="READY_FOR_INSPECTION",
                      data_source="synthetic_seed")
        db.add(order)
        db.flush()
        for index, (pid, quantity) in enumerate((("packing-blue-box", 2), ("packing-red-can", 1),
                                                 ("packing-yellow-pouch", 1))):
            db.add(OrderItem(id=f"item-packing-{suffix}-{index}", order_id=order.id,
                             product_id=pid, quantity=quantity))
    audit(db, "PACKING_DEMO_SEEDED", "demo", {"orders": 2, "provenance": "SYNTHETIC"})
    db.commit()
    return True
