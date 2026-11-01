import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from sqlalchemy import select

from backend.app.models.database import Base, Inventory, Order, Product, connect_database
from backend.app.services.synthetic_registration import register_synthetic_manifest, validate_synthetic_manifest


class SyntheticRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("blue", "red", "yellow", "green", "before"):
            Image.new("RGB", (320, 320), name if name != "before" else "white").save(self.root / f"{name}.png")
        self.data = {"dataset_id": "test", "provenance": "SYNTHETIC", "generator": "Claude AI", "rights_confirmed": True,
                     "products": [{"sku": sku, "name": name, "visible_label": sku, "reference_image": f"{name}.png",
                                   "inventory_quantity": 10, "inventory_location": "Synthetic test inventory"}
                                  for sku, name in (("BLUE-BOX", "blue"), ("RED-CAN", "red"),
                                                    ("YELLOW-POUCH", "yellow"), ("GREEN-CUBE", "green"))],
                     "order": {"reference": "CLAUDE-TEST", "items": {"BLUE-BOX": 2, "RED-CAN": 1, "YELLOW-POUCH": 1}},
                     "before_image": "before.png", "after_image": ""}
        self.path = self.root / "manifest.json"
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.data), encoding="utf-8")

    def test_rejects_physical_provenance_and_wrong_stock(self):
        self.data["provenance"] = "PHYSICAL_CAPTURE"
        self.save()
        with self.assertRaises(ValueError):
            validate_synthetic_manifest(self.path)
        self.data["provenance"] = "SYNTHETIC"
        self.data["products"][0]["inventory_quantity"] = 11
        self.save()
        with self.assertRaises(ValueError):
            validate_synthetic_manifest(self.path)

    def test_registers_isolated_catalog_and_order(self):
        engine, sessions = connect_database(f"sqlite:///{self.root / 'test.db'}")
        Base.metadata.create_all(engine)
        self.addCleanup(engine.dispose)
        with sessions() as db:
            result = register_synthetic_manifest(db, self.path, self.root / "data")
            self.assertEqual(result["products_registered"], 4)
            order = db.scalar(select(Order).where(Order.reference == "CLAUDE-TEST"))
            self.assertEqual(order.data_source, "synthetic_claude")
            self.assertIsNone(order.latest_inspection_id)
            product = db.scalar(select(Product).where(Product.sku == "BLUE-BOX"))
            self.assertEqual(product.reference_provenance, "SYNTHETIC")
            self.assertEqual(db.scalar(select(Inventory).where(Inventory.product_id == product.id)).quantity_available, 10)
        with sessions() as db:
            with self.assertRaises(ValueError):
                register_synthetic_manifest(db, self.path, self.root / "data")
