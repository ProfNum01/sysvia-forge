from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.services.seed import seed_demo
from model_fixtures import grounded_visual_result


def picture(color="white"):
    output = io.BytesIO()
    Image.new("RGB", (32, 32), color).save(output, "PNG")
    return output.getvalue()


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = Settings(database_url=f"sqlite:///{Path(self.temp.name) / 'test.db'}",
                                 data_dir=Path(self.temp.name), operator_token="unit-supervisor-token")
        self.app = create_app(self.settings)
        self.client_context = TestClient(self.app)
        self.client = self.client_context.__enter__()
        with self.app.state.sessions() as db:
            seed_demo(db)
        self.auth = {"Authorization": "Bearer unit-supervisor-token"}

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.app.state.engine.dispose()
        self.temp.cleanup()

    def upload(self, color="white", parent=None):
        url = f"/api/inspections/{parent}/reinspect" if parent else "/api/inspections"
        return self.client.post(url, data={"order_id": "order-1001", "rights_confirmed": "true"},
                                files={"image": ("test.png", picture(color), "image/png")}, headers=self.auth)

    def run_model(self, inspection_id, quantity=2, certain=True):
        response = grounded_visual_result(quantity, certain=certain)
        with patch("backend.app.api.routes.run_visual_models", return_value=response):
            return self.client.post(f"/api/inspections/{inspection_id}/analyze", headers=self.auth)

    def test_health_database_and_controlled_seed(self):
        self.assertEqual(self.client.get("/api/health").json()["database"], "ready")
        self.assertEqual(len(self.client.get("/api/orders").json()), 5)
        with self.app.state.sessions() as db:
            seed_demo(db)
        self.assertEqual(len(self.client.get("/api/orders").json()), 5)
        dashboard = self.client.get("/api/dashboard/summary").json()
        self.assertEqual(dashboard["verified_orders"], 0)
        self.assertEqual(dashboard["recent_inspections"], [])

    def test_order_details_use_database_products(self):
        order = self.client.get("/api/orders/order-1001").json()
        self.assertEqual(order["items"][0]["product"]["sku"], "PS-RED-01")
        self.assertEqual(order["items"][0]["quantity"], 2)
        self.assertEqual(self.client.get("/api/orders/missing").status_code, 404)

    def test_image_type_and_rights_validation(self):
        bad = self.client.post("/api/inspections", data={"order_id": "order-1001", "rights_confirmed": "true"},
                               files={"image": ("bad.jpg", b"not an image", "image/jpeg")}, headers=self.auth)
        self.assertEqual(bad.status_code, 422)
        no_rights = self.client.post("/api/inspections", data={"order_id": "order-1001"},
                                    files={"image": ("a.png", picture(), "image/png")}, headers=self.auth)
        self.assertEqual(no_rights.status_code, 422)

    def test_upload_and_pending_state_have_no_fake_results(self):
        uploaded = self.upload()
        self.assertEqual(uploaded.status_code, 201)
        inspection = uploaded.json()
        self.assertEqual(inspection["status"], "UPLOADED")
        self.assertEqual(inspection["observations"], [])
        self.assertEqual(self.client.get(inspection["image_url"]).status_code, 200)

    def test_paid_model_operations_require_server_auth(self):
        inspection = self.upload().json()
        self.assertEqual(self.client.post(f"/api/inspections/{inspection['id']}/analyze").status_code, 403)
        self.assertEqual(self.client.post("/api/actions/nope/execute", json={"idempotency_key": "key-12345678"}).status_code, 403)
        self.assertEqual(self.client.post("/api/actions/nope/approve", json={"idempotency_key": "key-12345678"},
                                         headers={"X-Role": "supervisor"}).status_code, 403)

    def test_missing_credentials_are_explicit_provider_error(self):
        from proofsight.meta_api import MetaConfigurationError
        inspection = self.upload().json()
        with patch("backend.app.api.routes.run_visual_models", side_effect=MetaConfigurationError("MODEL_API_KEY is not configured")):
            response = self.client.post(f"/api/inspections/{inspection['id']}/analyze", headers=self.auth)
        self.assertEqual(response.status_code, 503)
        saved = self.client.get(f"/api/inspections/{inspection['id']}").json()
        self.assertEqual(saved["status"], "PROVIDER_ERROR")
        self.assertEqual(saved["observations"], [])

    def test_exact_evidence_can_verify_and_cannot_reanalyze(self):
        inspection = self.upload().json()
        result = self.run_model(inspection["id"])
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["status"], "VERIFIED")
        self.assertEqual(self.run_model(inspection["id"]).status_code, 409)

    def test_uncertainty_never_verifies(self):
        inspection = self.upload().json()
        result = self.run_model(inspection["id"], certain=False).json()
        self.assertEqual(result["status"], "NEEDS_REVIEW")
        self.assertTrue(result["discrepancies"])

    def test_not_observed_is_not_absent(self):
        from backend.app.services.reconciliation import reconcile
        expected = [{"product_id": "p", "sku": "SKU-1", "quantity": 1}]
        result = reconcile(expected, [], geometry_available=True)
        self.assertFalse(result["verified"])
        self.assertEqual(result["discrepancies"][0]["type"], "NOT_OBSERVED")
        self.assertIsNone(result["discrepancies"][0]["observed_quantity"])

    def test_shortfall_approval_idempotency_and_new_photo_required(self):
        inspection = self.upload().json()
        result = self.run_model(inspection["id"], quantity=1).json()
        self.assertEqual(result["status"], "NEEDS_REVIEW")
        discrepancy = next(d for d in result["discrepancies"] if d["type"] == "SHORTFALL")
        self.assertEqual(discrepancy["required_quantity"] - discrepancy["observed_quantity"], 1)
        action = result["actions"][0]
        execute = f"/api/actions/{action['id']}/execute"
        approve = f"/api/actions/{action['id']}/approve"
        key = {"idempotency_key": "approval-12345678"}
        self.assertEqual(self.client.post(execute, json=key, headers=self.auth).status_code, 409)
        self.assertEqual(self.client.post(approve, json=key, headers=self.auth).status_code, 200)
        self.assertEqual(self.client.post(approve, json=key, headers=self.auth).status_code, 200)
        execution = {"idempotency_key": "execution-12345678"}
        self.assertEqual(self.client.post(execute, json=execution, headers=self.auth).status_code, 200)
        self.assertEqual(self.client.post(execute, json=execution, headers=self.auth).status_code, 200)
        self.assertEqual(self.client.get("/api/orders/order-1001").json()["status"], "HELD")
        self.assertEqual(self.upload(parent=inspection["id"]).status_code, 409)
        new = self.upload(color="blue", parent=inspection["id"]).json()
        self.assertNotEqual(new["photo_id"], inspection["photo_id"])
        self.assertEqual(new["previous_inspection_id"], inspection["id"])
        self.assertEqual(self.run_model(new["id"]).json()["status"], "VERIFIED")
        old = self.client.get(f"/api/inspections/{inspection['id']}").json()
        self.assertTrue(all(d["status"] == "RESOLVED" for d in old["discrepancies"]))

    def test_stale_actions_cannot_be_approved(self):
        inspection = self.upload().json()
        result = self.run_model(inspection["id"], quantity=1).json()
        action_id = result["actions"][0]["id"]
        self.upload(color="blue", parent=inspection["id"])
        response = self.client.post(f"/api/actions/{action_id}/approve",
                                    json={"idempotency_key": "approval-12345678"}, headers=self.auth)
        self.assertEqual(response.status_code, 409)

    def test_status_never_exposes_credentials(self):
        result = self.client.get("/api/integrations/meta/status")
        self.assertNotIn("unit-supervisor-token", result.text)
        self.assertNotIn("api_key", result.json())

    def test_startup_rebases_evidence_paths_when_moving_between_hosts(self):
        from backend.app.models.database import Inspection
        inspection = self.upload().json()
        canonical = self.settings.data_dir / "uploads" / f"{inspection['photo_id']}.png"
        with self.app.state.sessions() as db:
            row = db.get(Inspection, inspection["id"])
            row.image_path = "C:\\another-host\\uploads\\" + inspection["photo_id"] + ".png"
            db.commit()
        moved = create_app(self.settings)
        with TestClient(moved) as client:
            with moved.state.sessions() as db:
                self.assertEqual(db.get(Inspection, inspection["id"]).image_path, str(canonical))
            response = client.get(f"/api/inspections/{inspection['id']}/image")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, canonical.read_bytes())


if __name__ == "__main__":
    unittest.main()
