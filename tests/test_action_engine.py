"""Controlled proposals and transactional execution tests; no live model calls."""
import io
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select, func

from backend.app.main import create_app
from backend.app.core.config import Settings
from backend.app.models.database import Approval, CorrectiveAction, Inspection, Inventory, AuditEvent, PickingTask
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
                    output = io.BytesIO()
                    Image.new("RGB", (32, 32), "blue").save(output, "PNG")
                    replacement = self.client.post(f"/api/inspections/{inspection['id']}/reinspect", headers=self.auth,
                        data={"rights_confirmed": "true"}, files={"image": ("new.png", output.getvalue(), "image/png")})
                    self.assertEqual(replacement.status_code, 409)
                finally:
                    release.set()
                self.assertEqual(future.result(timeout=10).status_code, 200)
        self.assertEqual(len(requests), 1)

    def test_held_or_unverified_order_cannot_transition_to_shipping(self):
        inspection = self.inspection()
        response = self.client.post("/api/orders/order-1001/shipping-transition", headers=self.auth,
            json={"idempotency_key": "shipping-attempt-123", "target": "READY_TO_SHIP"})
        self.assertEqual(response.status_code, 409)

    def test_uncertain_evidence_allows_escalation_but_never_picking(self):
        inspection = self.inspection(certain=False)
        self.assertEqual(self.investigate(inspection, self.proposal(inspection)).status_code, 422)
        safe = self.proposal(inspection, action_type="ESCALATE_TO_HUMAN", product_id=None, quantity=None)
        response = self.investigate(inspection, safe)
        self.assertEqual(response.status_code, 200)
        self.assertIn("ESCALATE_TO_HUMAN", [row["type"] for row in response.json()["actions"]])
        self.assertNotIn("CREATE_PICKING_TASK", [row["type"] for row in response.json()["actions"]])

    def test_existing_held_order_is_a_real_null_quantity_operational_constraint(self):
        inspection = self.inspection(certain=False)
        hold = inspection["actions"][0]
        self.client.post(f"/api/actions/{hold['id']}/approve", headers=self.auth,
                         json={"idempotency_key": "existing-hold-approval"})
        self.client.post(f"/api/actions/{hold['id']}/execute", headers=self.auth,
                         json={"idempotency_key": "existing-hold-execute"})
        proposal = self.proposal(inspection, action_type="REQUEST_REINSPECTION", product_id=None, quantity=None)
        proposal.evidence_references.append("order:order-1001")
        proposal.findings.append({"type": "OPERATIONAL_CONSTRAINT", "product_id": None, "quantity": None,
                                  "evidence_references": ["order:order-1001"]})
        result = self.investigate(inspection, proposal)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["investigation_result"]["findings"][0]["quantity"], None)

    def test_insufficient_stock_cannot_be_overridden_by_model(self):
        inspection = self.inspection()
        with self.app.state.sessions() as db:
            inventory = db.scalar(select(Inventory).where(Inventory.product_id == "product-red"))
            inventory.quantity_available = 0
            db.commit()
        self.assertEqual(self.investigate(inspection, self.proposal(inspection)).status_code, 422)
        with self.app.state.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(PickingTask)), 0)

    def test_finding_quantity_and_product_region_references_are_cross_checked(self):
        inspection = self.inspection()
        bad_finding = self.proposal(inspection)
        bad_finding.findings.append({"type": "SHORTFALL", "product_id": "product-red", "quantity": 999,
                                    "evidence_references": bad_finding.evidence_references})
        self.assertEqual(self.investigate(inspection, bad_finding).status_code, 422)
        wrong_region = self.proposal(inspection)
        wrong_region.recommended_actions[0]["evidence_references"] = [
            f"discrepancy:{inspection['discrepancies'][0]['id']}", "inventory:product-red", "region:region-2"]
        self.assertEqual(self.investigate(inspection, wrong_region).status_code, 422)
        with self.app.state.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(CorrectiveAction).where(
                CorrectiveAction.type == "CREATE_PICKING_TASK")), 0)

    def test_concurrent_approval_and_execution_create_one_real_task(self):
        inspection = self.inspection()
        response = self.investigate(inspection, self.proposal(inspection)).json()
        task = next(row for row in response["actions"] if row["type"] == "CREATE_PICKING_TASK")
        for operation in ("approve", "execute"):
            path = f"/api/actions/{task['id']}/{operation}"
            body = {"idempotency_key": f"concurrent-{operation}-1234"}
            with ThreadPoolExecutor(max_workers=2) as executor:
                requests = [executor.submit(self.client.post, path, headers=self.auth, json=body) for _ in range(2)]
                responses = [pending.result(timeout=10) for pending in requests]
            self.assertEqual([row.status_code for row in responses], [200, 200])
        with self.app.state.sessions() as db:
            tasks = list(db.scalars(select(PickingTask)))
            self.assertEqual(len(tasks), 1)
            self.assertEqual((tasks[0].order_reference, tasks[0].product_reference, tasks[0].quantity, tasks[0].status),
                             ("PS-1001", "PS-RED-01", 1, "OPEN"))
            self.assertIsNotNone(db.get(Approval, tasks[0].approval_id))
            inventory = db.scalar(select(Inventory).where(Inventory.product_id == "product-red"))
            self.assertEqual(inventory.quantity_available, 20)
            self.assertEqual(db.scalar(select(func.count()).select_from(AuditEvent).where(
                AuditEvent.entity_id == task["id"], AuditEvent.event_type == "CONTROLLED_ACTION_EXECUTED")), 1)

    def test_safe_actions_hold_shipping_until_distinct_verified_reinspection(self):
        inspection = self.inspection()
        proposal = self.proposal(inspection, action_type="HOLD_SHIPMENT", quantity=None, product_id=None)
        for action_type in ("REQUEST_REINSPECTION", "ESCALATE_TO_HUMAN"):
            proposal.recommended_actions.append({"type": action_type, "quantity": None, "product_id": None,
                "requires_approval": True, "evidence_references": proposal.evidence_references})
        result = self.investigate(inspection, proposal)
        self.assertEqual(result.status_code, 200)
        actions = result.json()["actions"]
        self.assertEqual(sum(row["type"] in {"HOLD_ORDER", "HOLD_SHIPMENT"} for row in actions), 1)
        for action in actions:
            self.assertEqual(self.client.post(f"/api/actions/{action['id']}/approve", headers=self.auth,
                json={"idempotency_key": f"approve-{action['id']}"}).status_code, 200)
            response = self.client.post(f"/api/actions/{action['id']}/execute", headers=self.auth,
                json={"idempotency_key": f"execute-{action['id']}"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["lifecycle_state"], "AWAITING_REINSPECTION")
        denied = self.client.post("/api/orders/order-1001/shipping-transition", headers=self.auth,
            json={"idempotency_key": "still-held-shipping-123", "target": "READY_TO_SHIP"})
        self.assertEqual(denied.status_code, 409)
        output = io.BytesIO()
        Image.new("RGB", (32, 32), "blue").save(output, "PNG")
        replacement = self.client.post(f"/api/inspections/{inspection['id']}/reinspect", headers=self.auth,
            data={"rights_confirmed": "true"}, files={"image": ("new.png", output.getvalue(), "image/png")})
        self.assertEqual(replacement.status_code, 201)
        with patch("backend.app.api.routes.run_visual_models", return_value=grounded_visual_result()):
            verified = self.client.post(f"/api/inspections/{replacement.json()['id']}/analyze", headers=self.auth)
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(verified.json()["status"], "VERIFIED")
        old = self.client.get(f"/api/inspections/{inspection['id']}").json()
        for action in old["actions"]:
            self.assertEqual(action["lifecycle_state"], "RESOLVED_BY_REINSPECTION")
            self.assertEqual(action["execution_details"]["resolved_by_photo_id"], replacement.json()["photo_id"])
            self.assertEqual(action["execution_details"]["previous_photo_id"], inspection["photo_id"])
            self.assertFalse(action["execution_details"]["reinspection_required"])
        ready = self.client.post("/api/orders/order-1001/shipping-transition", headers=self.auth,
            json={"idempotency_key": "verified-ready-123", "target": "READY_TO_SHIP"})
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(ready.json()["shipping_status"], "READY_TO_SHIP")

    def test_timeout_is_persisted_and_explicit_retry_reuses_investigation_id(self):
        inspection = self.inspection()
        path = f"/api/inspections/{inspection['id']}/investigate"
        headers = {**self.auth, "Idempotency-Key": "retry-investigation-123"}
        with patch("backend.app.api.routes.investigate_with_read_tools", side_effect=TimeoutError("sensitive-value")):
            response = self.client.post(path, headers=headers)
        self.assertEqual(response.status_code, 504)
        failed = self.client.get(f"/api/inspections/{inspection['id']}").json()
        self.assertEqual(failed["investigation_status"], "FAILED")
        self.assertTrue(failed["investigation_error"]["retryable"])
        self.assertNotIn("sensitive-value", str(failed))
        with patch("backend.app.api.routes.investigate_with_read_tools", return_value=self.proposal(inspection)):
            retried = self.client.post(path, headers=headers)
        self.assertEqual(retried.status_code, 200)
        self.assertEqual(retried.json()["investigation_id"], failed["investigation_id"])

    def test_legacy_action_check_upgrade_retains_approval_and_existing_hold(self):
        inspection = self.inspection()
        hold = next(row for row in inspection["actions"] if row["type"] == "HOLD_ORDER")
        self.client.post(f"/api/actions/{hold['id']}/approve", headers=self.auth,
                         json={"idempotency_key": "legacy-approval-123"})
        self.client.post(f"/api/actions/{hold['id']}/execute", headers=self.auth,
                         json={"idempotency_key": "legacy-execution-123"})
        self.context.__exit__(None, None, None)
        self.app.state.engine.dispose()
        database_file = self.settings.data_dir / "proofsight.db"
        with closing(sqlite3.connect(database_file)) as db, db:
            db.execute("PRAGMA foreign_keys=OFF")
            db.executescript("""CREATE TABLE corrective_actions_legacy (
                id VARCHAR PRIMARY KEY, inspection_id VARCHAR NOT NULL REFERENCES inspections(id), product_id VARCHAR,
                quantity INTEGER, type VARCHAR NOT NULL CHECK(type IN ('HOLD_ORDER','CREATE_PICKING_TASK')),
                status VARCHAR NOT NULL, proposal TEXT NOT NULL, execution_key VARCHAR UNIQUE,
                execution_details JSON, created_at VARCHAR NOT NULL);
                INSERT INTO corrective_actions_legacy SELECT id,inspection_id,product_id,quantity,type,status,proposal,
                    execution_key,execution_details,created_at FROM corrective_actions;
                DROP TABLE corrective_actions;
                ALTER TABLE corrective_actions_legacy RENAME TO corrective_actions;""")
        self.app = create_app(self.settings)
        self.context = TestClient(self.app)
        self.client = self.context.__enter__()
        for startup in range(2):
            if startup:
                self.context.__exit__(None, None, None)
                self.app = create_app(self.settings)
                self.context = TestClient(self.app)
                self.client = self.context.__enter__()
            with self.app.state.sessions() as db:
                retained = db.get(CorrectiveAction, hold["id"])
                self.assertEqual((retained.status, retained.lifecycle_state), ("EXECUTED", "AWAITING_REINSPECTION"))
                approval = db.scalar(select(Approval).where(Approval.action_id == retained.id))
                self.assertEqual(approval.idempotency_key, "legacy-approval-123")
                self.assertEqual(db.connection().exec_driver_sql("PRAGMA foreign_key_check").fetchall(), [])
                if not startup:
                    db.add(CorrectiveAction(inspection_id=inspection["id"], type="HOLD_SHIPMENT", proposal="Constraint migration fixture"))
                    db.commit()
            self.assertEqual(self.client.get("/api/orders/order-1001").json()["status"], "HELD")
