"""Controlled proposals and transactional execution tests; no live model calls."""
import io
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select, func

from backend.app.main import create_app
from backend.app.core.config import Settings
from backend.app.models.database import CorrectiveAction, Inspection, Inventory, AuditEvent
from backend.app.services.seed import seed_demo
from model_fixtures import grounded_visual_result


class ActionEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = Settings(data_dir=Path(self.temp.name), operator_token="action-test-token")
        self.app = create_app(self.settings)
        self.context = TestClient(self.app)
        self.client = self.context.__enter__()
        with self.app.state.sessions() as db:
            seed_demo(db)
        self.auth = {"Authorization": "Bearer action-test-token"}

    def tearDown(self):
        self.context.__exit__(None, None, None)
        self.app.state.engine.dispose()
        self.temp.cleanup()

    def inspection(self, certain=True):
        output = io.BytesIO()
        Image.new("RGB", (32, 32), "white").save(output, "PNG")
        uploaded = self.client.post("/api/inspections", headers=self.auth,
            data={"order_id": "order-1001", "rights_confirmed": "true"},
            files={"image": ("fixture.png", output.getvalue(), "image/png")})
        self.assertEqual(uploaded.status_code, 201)
        with patch("backend.app.api.routes.run_visual_models", return_value=grounded_visual_result(1, certain=certain)):
            result = self.client.post(f"/api/inspections/{uploaded.json()['id']}/analyze", headers=self.auth)
        self.assertEqual(result.status_code, 200)
        return result.json()

    def proposal(self, inspection, action_type="CREATE_PICKING_TASK", quantity=1, product_id="product-red"):
        refs = [f"inspection:{inspection['id']}", f"photo:{inspection['photo_id']}"]
        refs += [f"discrepancy:{row['id']}" for row in inspection["discrepancies"]]
        refs += [f"region:{row['id']}" for row in inspection["regions"]]
        refs += ["inventory:product-red"]
        payload = {"summary": "Mock investigation supported by recorded evidence.", "recommendation": "REQUEST_REVIEW",
            "decision": "CORRECTIVE_ACTION_REQUIRED", "findings": [], "verification_required": True,
            "evidence_references": refs, "recommended_actions": [{"type": action_type,
                "product_id": product_id, "quantity": quantity, "requires_approval": True,
                "evidence_references": refs}]}
        return SimpleNamespace(**payload, model_dump=lambda: payload)

    def investigate(self, inspection, proposal):
        with patch("backend.app.api.routes.investigate_with_read_tools", return_value=proposal):
            return self.client.post(f"/api/inspections/{inspection['id']}/investigate", headers=self.auth)

    def test_structured_proposal_is_persisted_and_cannot_run_without_approval(self):
        inspection = self.inspection()
        response = self.investigate(inspection, self.proposal(inspection))
        self.assertEqual(response.status_code, 200)
        saved = response.json()
        self.assertEqual(saved["investigation_status"], "COMPLETED")
        self.assertEqual(saved["investigation_result"]["decision"], "CORRECTIVE_ACTION_REQUIRED")
        task = next(a for a in saved["actions"] if a["type"] == "CREATE_PICKING_TASK")
        self.assertEqual(task["status"], "PENDING_APPROVAL")
        self.assertEqual(self.client.post(f"/api/actions/{task['id']}/execute", headers=self.auth,
            json={"idempotency_key": "unapproved-task-123"}).status_code, 409)

    def test_invalid_model_product_quantity_or_uncertainty_cannot_create_picking(self):
        inspection = self.inspection()
        for product_id, quantity in (("product-outside", 1), ("product-red", 99), ("product-red", -1)):
            with self.subTest(product_id=product_id, quantity=quantity):
                response = self.investigate(inspection, self.proposal(inspection, product_id=product_id, quantity=quantity))
                self.assertEqual(response.status_code, 422)
                with self.app.state.sessions() as db:
                    self.assertEqual(db.scalar(select(func.count()).select_from(CorrectiveAction).where(
                        CorrectiveAction.type == "CREATE_PICKING_TASK")), 0)

    def test_rejected_action_is_idempotent_and_cannot_execute(self):
        inspection = self.inspection()
        investigated = self.investigate(inspection, self.proposal(inspection)).json()
        task = next(a for a in investigated["actions"] if a["type"] == "CREATE_PICKING_TASK")
        path = f"/api/actions/{task['id']}/reject"
        body = {"idempotency_key": "reject-task-1234", "reason": "Need a clearer physical count."}
        self.assertEqual(self.client.post(path, headers={"X-Role": "supervisor"}, json=body).status_code, 403)
        self.assertEqual(self.client.post(path, headers=self.auth, json=body).json()["status"], "REJECTED")
        self.assertEqual(self.client.post(path, headers=self.auth, json=body).status_code, 200)
        self.assertEqual(self.client.post(f"/api/actions/{task['id']}/execute", headers=self.auth,
            json={"idempotency_key": "execute-rejected-123"}).status_code, 409)

    def test_investigation_progress_is_pollable_and_duplicate_request_does_not_call_model(self):
        inspection = self.inspection()
        entered, release = threading.Event(), threading.Event()
        requests = []
        proposal = self.proposal(inspection)

        def investigate(_db, _inspection, _order, on_event=None):
            requests.append(True)
            on_event("TOOL_CALLED", {"tool": "get_order_details", "order_id": "order-1001"})
            entered.set()
            if not release.wait(10):
                raise TimeoutError()
            return proposal

        path = f"/api/inspections/{inspection['id']}/investigate"
        with patch("backend.app.api.routes.investigate_with_read_tools", side_effect=investigate):
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.client.post, path, headers=self.auth)
                try:
                    self.assertTrue(entered.wait(10))
                    progress = self.client.get(f"/api/inspections/{inspection['id']}").json()
                    self.assertEqual(progress["investigation_status"], "RUNNING")
                    self.assertIn("TOOL_CALLED", [row["event_type"] for row in progress["execution_events"]])
                    self.assertEqual(self.client.post(path, headers=self.auth).status_code, 200)
                finally:
                    release.set()
                self.assertEqual(future.result(timeout=10).status_code, 200)
        self.assertEqual(len(requests), 1)

    def test_held_or_unverified_order_cannot_transition_to_shipping(self):
        inspection = self.inspection()
        response = self.client.post("/api/orders/order-1001/shipping-transition", headers=self.auth,
            json={"idempotency_key": "shipping-attempt-123", "target": "READY_TO_SHIP"})
        self.assertEqual(response.status_code, 409)
