import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from sqlalchemy import select
from fastapi.testclient import TestClient

from backend.app.models.database import Base, Order, Product, connect_database
from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.services.physical_registration import validate_physical_manifest, register_physical_manifest


class PhysicalRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.joinpath("references").mkdir()
        self.root.joinpath("captures").mkdir()
        for name in ("blue", "red", "yellow", "green"):
            Image.new("RGB", (320, 320), name if name != "yellow" else "yellow").save(self.root / "references" / f"{name}.png")
        for name in ("before", "after"):
            Image.new("RGB", (640, 480), "white" if name == "before" else "gray").save(self.root / "captures" / f"{name}.png")
        self.manifest = {
            "dataset_id": "owner-physical-001", "provenance": "PHYSICAL_CAPTURE",
            "products": [{"sku": sku, "name": name, "reference_image": f"references/{name}.png",
                          "visible_label": sku, "barcode": None, "inventory_quantity": 2,
                          "inventory_location": "Owner rack"}
                         for sku, name in (("BLUE-BOX", "blue"), ("RED-CAN", "red"),
                                           ("YELLOW-POUCH", "yellow"), ("GREEN-CUBE", "green"))],
            "order": {"reference": "PHYSICAL-001", "items": {"BLUE-BOX": 2, "RED-CAN": 1, "YELLOW-POUCH": 1}},
            "before_image": "captures/before.png", "after_image": "captures/after.png",
            "rights_confirmed": True,
        }
        self.path = self.root / "manifest.json"
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.manifest), encoding="utf-8")

    def test_rejects_synthetic_or_missing_rights_and_path_escape(self):
        self.manifest["provenance"] = "SYNTHETIC"
        self.save()
        with self.assertRaises(ValueError):
            validate_physical_manifest(self.path)

        self.manifest["provenance"] = "PHYSICAL_CAPTURE"
        self.manifest["rights_confirmed"] = False
        self.save()
        with self.assertRaises(ValueError):
            validate_physical_manifest(self.path)
        self.manifest["rights_confirmed"] = True
        self.manifest["products"][0]["reference_image"] = "../outside.png"
        self.save()
        with self.assertRaises(ValueError):
            validate_physical_manifest(self.path)

    def test_rejects_identical_before_after_bytes(self):
        (self.root / "captures" / "after.png").write_bytes((self.root / "captures" / "before.png").read_bytes())
        with self.assertRaises(ValueError):
            validate_physical_manifest(self.path)

    def test_accepts_before_capture_before_correction(self):
        self.manifest["after_image"] = ""
        self.save()
        self.assertEqual(validate_physical_manifest(self.path)["after_image"], "")

    def test_registers_separate_catalog_and_order_without_inspection(self):
        engine, sessions = connect_database(f"sqlite:///{self.root / 'test.db'}")
        Base.metadata.create_all(engine)
        self.addCleanup(engine.dispose)
        with sessions() as db:
            result = register_physical_manifest(db, self.path, self.root / "data")
            self.assertEqual(result["products_registered"], 4)
            self.assertEqual(db.scalar(select(Product).where(Product.sku == "BLUE-BOX")).reference_provenance,
                             "PHYSICAL_CAPTURE")
            order = db.scalar(select(Order).where(Order.reference == "PHYSICAL-001"))
            self.assertEqual(order.data_source, "physical_capture")
            self.assertIsNone(order.latest_inspection_id)
        with sessions() as db:
            with self.assertRaises(ValueError):
                register_physical_manifest(db, self.path, self.root / "data")

    def test_registered_reference_requires_operator_authorization(self):
        Image.new("RGB", (320, 320), "blue").save(self.root / "references" / "blue.jpg", "JPEG")
        self.manifest["products"][0]["reference_image"] = "references/blue.jpg"
        self.save()
        settings = Settings(database_url=f"sqlite:///{self.root / 'api.db'}", data_dir=self.root / "data",
                            operator_token="physical-test-token")
        app = create_app(settings)
        with TestClient(app) as client:
            with app.state.sessions() as db:
                register_physical_manifest(db, self.path, settings.data_dir)
            url = "/api/products/physical-blue-box/reference"
            self.assertEqual(client.get(url).status_code, 403)
            response = client.get(url, headers={"Authorization": "Bearer physical-test-token"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["content-type"], "image/png")
            self.assertTrue(response.content.startswith(b"\x89PNG"))
        app.state.engine.dispose()
