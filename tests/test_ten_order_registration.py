from pathlib import Path

from sqlalchemy import select

from backend.app.models.database import Base, Order, Product, connect_database
from backend.app.services.ten_order_registration import register_ten_orders


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "evaluation/datasets/ten-orders/manifest.json"


def test_registers_ten_orders_idempotently(tmp_path):
    engine, sessions = connect_database(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    with sessions() as db:
        for sku in ("BLUE-BOX", "RED-CAN", "YELLOW-POUCH", "GREEN-CUBE"):
            db.add(Product(id=f"claude-{sku.lower()}", sku=sku, name=sku, color="", description="fixture",
                           reference_provenance="SYNTHETIC", visible_label=sku))
        db.commit()
        assert register_ten_orders(db, MANIFEST) == 10
        assert register_ten_orders(db, MANIFEST) == 0
        orders = list(db.scalars(select(Order).where(Order.reference.like("TEN-ORDER-%"))))
        assert len(orders) == 10
        assert all(o.data_source == "synthetic_claude" and o.latest_inspection_id is None for o in orders)
        assert all(o.shipping_status == "NOT_READY" for o in orders)
    engine.dispose()
