from __future__ import annotations

import asyncio
import io
import json
import random
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from openai import OpenAI
from PIL import Image
from sqlalchemy import func, select

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.models.database import Approval, AuditEvent, CorrectiveAction, Inspection, Inventory, Order
from backend.app.services.investigation import InvestigationSummary, investigate_with_read_tools
from backend.app.services.inventory import available_quantity
from backend.app.services.seed import seed_demo
from proofsight.meta_api import MetaConfig, MetaConfigurationError
from model_fixtures import grounded_visual_result


def image_bytes(color="white"):
    output = io.BytesIO()
    Image.new("RGB", (32, 32), color).save(output, "PNG")
    return output.getvalue()


def verified_visual_result():
    return grounded_visual_result()


class BackendSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = Settings(database_url=f"sqlite:///{Path(self.temp.name) / 'safety.db'}",
                                 data_dir=Path(self.temp.name), operator_token="safety-supervisor-token",
                                 max_upload_bytes=1500)
        self.app = create_app(self.settings)
        self.context = TestClient(self.app)
        self.client = self.context.__enter__()
        with self.app.state.sessions() as db:
            seed_demo(db)
        self.auth = {"Authorization": "Bearer safety-supervisor-token"}

    def tearDown(self):
        self.context.__exit__(None, None, None)
        self.app.state.engine.dispose()
        self.temp.cleanup()

    def upload(self, *, parent=None, color="white", headers=None):
        path = f"/api/inspections/{parent}/reinspect" if parent else "/api/inspections"
        return self.client.post(path, data={"order_id": "order-1001", "rights_confirmed": "true"},
                                files={"image": ("evidence.png", image_bytes(color), "image/png")},
                                headers=self.auth if headers is None else headers)

    def retryable_inspection(self):
        uploaded = self.upload()
        self.assertEqual(uploaded.status_code, 201)
        inspection = uploaded.json()
        with patch("backend.app.api.routes.run_visual_models", side_effect=MetaConfigurationError("missing")):
            failed = self.client.post(f"/api/inspections/{inspection['id']}/analyze", headers=self.auth)
        self.assertEqual(failed.status_code, 503)
        return inspection

    def shortfall_inspection(self):
        uploaded = self.upload()
        self.assertEqual(uploaded.status_code, 201)
        result = grounded_visual_result(red_quantity=1)
        with patch("backend.app.api.routes.run_visual_models", return_value=result):
            analyzed = self.client.post(f"/api/inspections/{uploaded.json()['id']}/analyze", headers=self.auth)
        self.assertEqual(analyzed.status_code, 200)
        self.assertEqual(analyzed.json()["status"], "NEEDS_REVIEW")
        return analyzed.json()

    def test_upload_requires_real_authorization_and_cannot_spoof_role(self):
        for headers in ({}, {"X-Role": "supervisor"}, {"Authorization": "Bearer incorrect-token"}):
            with self.subTest(headers=headers):
                self.assertEqual(self.upload(headers=headers).status_code, 403)
        with self.app.state.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Inspection)), 0)
        self.assertFalse((self.settings.data_dir / "uploads").exists())

    def test_reinspection_requires_authorization_before_replacing_evidence(self):
        old = self.retryable_inspection()
        for headers in ({}, {"X-Role": "supervisor"}, {"Authorization": "Bearer incorrect-token"}):
            with self.subTest(headers=headers):
                response = self.upload(parent=old["id"], color="blue", headers=headers)
                self.assertEqual(response.status_code, 403)
        order = self.client.get("/api/orders/order-1001").json()
        self.assertEqual(order["latest_inspection_id"], old["id"])
        with self.app.state.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Inspection)), 1)

    def test_inflight_provider_retry_blocks_concurrent_reinspection(self):
        old = self.retryable_inspection()
        entered, release = threading.Event(), threading.Event()

        def blocked_provider(*_args, **_kwargs):
            entered.set()
            if not release.wait(10):
                raise RuntimeError("Test provider barrier timed out")
            return verified_visual_result()

        with patch("backend.app.api.routes.run_visual_models", side_effect=blocked_provider):
            with ThreadPoolExecutor(max_workers=1) as executor:
                pending = executor.submit(self.client.post, f"/api/inspections/{old['id']}/analyze", headers=self.auth)
                try:
                    self.assertTrue(entered.wait(10), "Provider retry did not start")
                    self.assertEqual(self.upload(parent=old["id"], color="blue").status_code, 409)
                    duplicate = self.client.post(f"/api/inspections/{old['id']}/analyze", headers=self.auth)
                    self.assertEqual(duplicate.status_code, 409)
                    order = self.client.get("/api/orders/order-1001").json()
                    self.assertEqual(order["latest_inspection_id"], old["id"])
                    self.assertNotEqual(order["status"], "VERIFIED")
                finally:
                    release.set()
                self.assertEqual(pending.result(timeout=10).json()["status"], "VERIFIED")

    def test_invalidated_inflight_analysis_cannot_verify_replacement_photo(self):
        old = self.retryable_inspection()
        entered, release = threading.Event(), threading.Event()

        def blocked_provider(*_args, **_kwargs):
            entered.set()
            if not release.wait(10):
                raise RuntimeError("Test provider barrier timed out")
            return verified_visual_result()

        with patch("backend.app.api.routes.run_visual_models", side_effect=blocked_provider):
            with ThreadPoolExecutor(max_workers=1) as executor:
                pending = executor.submit(self.client.post, f"/api/inspections/{old['id']}/analyze", headers=self.auth)
                try:
                    self.assertTrue(entered.wait(10), "Provider retry did not start")
                    # Reproduce interrupted-analysis recovery while its previous provider call is returning.
                    with self.app.state.sessions() as db:
                        inspection = db.get(Inspection, old["id"])
                        inspection.status = "PROVIDER_ERROR"
                        inspection.provider_error = "Interrupted analysis recovered."
                        db.commit()
                    replacement = self.upload(parent=old["id"], color="blue")
                    self.assertEqual(replacement.status_code, 201)
                finally:
                    release.set()
                self.assertEqual(pending.result(timeout=10).status_code, 409)
        order = self.client.get("/api/orders/order-1001").json()
        self.assertEqual(order["status"], "PENDING_INSPECTION")
        self.assertEqual(order["latest_inspection_id"], replacement.json()["id"])
        self.assertEqual(replacement.json()["status"], "UPLOADED")
        saved_old = self.client.get(f"/api/inspections/{old['id']}").json()
        self.assertEqual(saved_old["status"], "PROVIDER_ERROR")
        self.assertEqual(saved_old["observations"], [])

    def test_compressed_upload_cannot_exceed_provider_limit_after_normalization(self):
        random_pixels = random.Random(2026).randbytes(32 * 32 * 3)
        output = io.BytesIO()
        Image.frombytes("RGB", (32, 32), random_pixels).save(output, "JPEG", quality=50)
        jpeg = output.getvalue()
        self.assertLess(len(jpeg), 1500)
        normalized = io.BytesIO()
        with Image.open(io.BytesIO(jpeg)) as image:
            image.convert("RGB").save(normalized, "PNG")
        self.assertGreater(len(normalized.getvalue()), 1500)
        response = self.client.post("/api/inspections", headers=self.auth,
                                    data={"order_id": "order-1001", "rights_confirmed": "true"},
                                    files={"image": ("compressed.jpg", jpeg, "image/jpeg")})
        self.assertEqual(response.status_code, 422)
        with self.app.state.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Inspection)), 0)
        self.assertFalse((self.settings.data_dir / "uploads").exists())

    def test_chunked_body_without_content_length_is_bounded(self):
        chunks = [b'{"idempotency_key":"oversized-12345678","padding":"']
        chunks.extend([b"x" * 65536] * 20)
        chunks.append(b'"}')
        messages = iter([{"type": "http.request", "body": chunk, "more_body": index < len(chunks) - 1}
                         for index, chunk in enumerate(chunks)])
        sent = []

        async def receive():
            await asyncio.sleep(0)
            return next(messages, {"type": "http.disconnect"})

        async def send(message):
            sent.append(message)

        scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
                 "method": "POST", "scheme": "http", "path": "/api/actions/missing/execute",
                 "raw_path": b"/api/actions/missing/execute", "query_string": b"", "root_path": "",
                 "server": ("testserver", 80), "client": ("127.0.0.1", 12345),
                 "headers": [(b"content-type", b"application/json"), (b"transfer-encoding", b"chunked"),
                             (b"authorization", b"Bearer safety-supervisor-token")]}
        asyncio.run(self.app(scope, receive, send))
        statuses = [message["status"] for message in sent if message["type"] == "http.response.start"]
        self.assertEqual(statuses, [413])

    def test_picking_task_requires_approval_reserves_stock_and_still_needs_new_evidence(self):
        inspection = self.shortfall_inspection()
        with self.app.state.sessions() as db:
            inventory = db.scalar(select(Inventory).where(Inventory.product_id == "product-red"))
            inventory.quantity_available = 1
            db.commit()
        # The structured recommendation remains subject to the database shortfall and stock policy.
        refs = [f"inspection:{inspection['id']}", f"photo:{inspection['photo_id']}", "inventory:product-red"]
        refs += [f"discrepancy:{row['id']}" for row in inspection["discrepancies"]]
        refs += [f"region:{row['id']}" for row in inspection["regions"]]
        summary = InvestigationSummary(summary="One visible red unit; review the stock location.",
            recommendation="REQUEST_REVIEW", decision="CORRECTIVE_ACTION_REQUIRED", evidence_references=refs,
            recommended_actions=[{"type": "CREATE_PICKING_TASK", "product_id": "product-red", "quantity": 1,
                "requires_approval": True, "evidence_references": refs}])
        with patch("backend.app.api.routes.investigate_with_read_tools", return_value=summary):
            investigated = self.client.post(f"/api/inspections/{inspection['id']}/investigate", headers=self.auth)
        self.assertEqual(investigated.status_code, 200)
        tasks = [action for action in investigated.json()["actions"] if action["type"] == "CREATE_PICKING_TASK"]
        self.assertEqual(len(tasks), 1)
        task = tasks[0]
        self.assertEqual((task["product_id"], task["quantity"], task["status"]), ("product-red", 1, "PENDING_APPROVAL"))
        execute_url = f"/api/actions/{task['id']}/execute"
        execution_key = {"idempotency_key": "picking-execution-12345678"}
        self.assertEqual(self.client.post(execute_url, json=execution_key, headers=self.auth).status_code, 409)
        approved = self.client.post(f"/api/actions/{task['id']}/approve", headers=self.auth,
                                    json={"idempotency_key": "picking-approval-12345678"})
        self.assertEqual(approved.status_code, 200)
        executed = self.client.post(execute_url, json=execution_key, headers=self.auth)
        self.assertEqual(executed.status_code, 200)
        self.assertEqual(executed.json()["status"], "EXECUTED")
        self.assertEqual(executed.json()["execution_details"]["status"], "OPEN")
        picking_id = executed.json()["execution_details"]["task_id"]
        completion = f"/api/picking-tasks/{picking_id}/complete"
        completion_body = {"idempotency_key": "physical-pick-report-12345678"}
        self.assertEqual(self.client.post(completion, json=completion_body).status_code, 403)
        self.assertEqual(self.client.post(completion, json=completion_body, headers=self.auth).status_code, 200)
        self.assertEqual(self.client.post(completion, json=completion_body, headers=self.auth).status_code, 200)
        self.assertEqual(self.client.get("/api/orders/order-1001").json()["shipping_status"], "HELD")
        self.assertTrue(executed.json()["execution_details"]["reinspection_required"])
        with self.app.state.sessions() as db:
            inventory = db.scalar(select(Inventory).where(Inventory.product_id == "product-red"))
            self.assertEqual(inventory.quantity_available, 1)
            self.assertEqual(available_quantity(db, "product-red"), 0)
            order = db.get(Order, "order-1001")
            self.assertEqual(order.status, "NEEDS_REVIEW")
            self.assertEqual(order.preparation_status, "PICKING_TASK_OPEN")
            self.assertEqual(db.get(Inspection, inspection["id"]).status, "NEEDS_REVIEW")
        replay = self.client.post(execute_url, json=execution_key, headers=self.auth)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.json(), executed.json())
        changed_key = self.client.post(execute_url, headers=self.auth,
                                       json={"idempotency_key": "other-execution-12345678"})
        self.assertEqual(changed_key.status_code, 409)
        with self.app.state.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(AuditEvent).where(
                AuditEvent.entity_id == task["id"], AuditEvent.event_type == "CONTROLLED_ACTION_EXECUTED")), 1)
            self.assertEqual(available_quantity(db, "product-red"), 0)
        self.assertEqual(self.upload(parent=inspection["id"]).status_code, 409)
        self.assertEqual(self.client.post(f"/api/inspections/{inspection['id']}/analyze", headers=self.auth).status_code, 409)
        replacement = self.upload(parent=inspection["id"], color="blue")
        self.assertEqual(replacement.status_code, 201)
        self.assertNotEqual(replacement.json()["photo_id"], inspection["photo_id"])
        self.assertEqual(replacement.json()["previous_inspection_id"], inspection["id"])
        self.assertNotEqual(self.client.get("/api/orders/order-1001").json()["status"], "VERIFIED")
        with patch("backend.app.api.routes.run_visual_models", return_value=verified_visual_result()):
            reinspected = self.client.post(f"/api/inspections/{replacement.json()['id']}/analyze", headers=self.auth)
        self.assertEqual(reinspected.status_code, 200)
        self.assertEqual(reinspected.json()["status"], "VERIFIED")
        original = self.client.get(f"/api/inspections/{inspection['id']}").json()
        self.assertEqual(original["photo_id"], inspection["photo_id"])
        self.assertEqual(original["resolved_by_inspection_id"], replacement.json()["id"])

    def test_read_tool_sdk_transport_uses_bound_database_reads_and_rejects_write_requests(self):
        inspection = self.shortfall_inspection()
        config = MetaConfig(api_key="synthetic-transport-test-key")

        def completion(*, name=None, arguments="{}"):
            message = {"role": "assistant", "content": None}
            if name:
                message["tool_calls"] = [{"id": f"call-{name}", "type": "function",
                                           "function": {"name": name, "arguments": arguments}}]
            else:
                reference = "inspection:" + inspection["id"]
                message["content"] = json.dumps({"summary": "One visible red unit needs review.",
                    "recommendation": "REQUEST_REVIEW", "decision": "HUMAN_REVIEW_REQUIRED", "findings": [],
                    "recommended_actions": [{"type": "ESCALATE_TO_HUMAN", "product_id": None, "quantity": None,
                        "requires_approval": True, "evidence_references": [reference]}],
                    "evidence_references": [reference], "verification_required": True})
            return httpx.Response(200, json={"id": "synthetic-completion", "object": "chat.completion",
                "created": 0, "model": "muse-spark-1.3", "choices": [{"index": 0, "message": message,
                "finish_reason": "tool_calls" if name else "stop"}]})

        requests = []

        def controlled_transport(request):
            payload = json.loads(request.content)
            requests.append(payload)
            if len(requests) == 1:
                return completion(name="get_order_details", arguments='{"order_id":"order-1001"}')
            if len(requests) == 2:
                return completion(name="get_inspection_results", arguments=json.dumps({"inspection_id": inspection["id"]}))
            if len(requests) == 3:
                return completion(name="check_inventory", arguments='{"product_id":"product-red"}')
            if len(requests) in (4, 5):
                return completion()
            raise AssertionError("Investigation exceeded its bounded read tool flow")

        client = OpenAI(api_key=config.api_key, base_url=config.base_url, max_retries=0,
                        http_client=httpx.Client(transport=httpx.MockTransport(controlled_transport)))
        with self.app.state.sessions() as db:
            order = db.get(Order, "order-1001")
            row = db.get(Inspection, inspection["id"])
            with patch("backend.app.services.investigation.MetaConfig.from_env", return_value=config), \
                 patch("backend.app.services.investigation.create_muse_client", return_value=client):
                summary = investigate_with_read_tools(db, row, order)
            self.assertEqual(summary.recommendation, "REQUEST_REVIEW")
            read_audits = list(db.scalars(select(AuditEvent.event_type).where(AuditEvent.entity_id == row.id)))
            self.assertIn("TOOL_CALLED", read_audits)
            self.assertIn("TOOL_COMPLETED", read_audits)
            self.assertEqual(db.scalar(select(func.count()).select_from(CorrectiveAction)), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(Approval)), 0)
            self.assertEqual(order.status, "NEEDS_REVIEW")
        self.assertEqual(len(requests), 5)
        self.assertEqual({tool["function"]["name"] for tool in requests[0]["tools"]},
            {"get_order_details", "get_inspection_results", "check_inventory", "get_pending_actions",
             "get_order_history", "get_verification_history"})
        self.assertEqual(requests[0]["tool_choice"], "auto")
        tool_results = {message["tool_call_id"]: json.loads(message["content"])
                        for message in requests[-1]["messages"] if message["role"] == "tool"}
        self.assertEqual(tool_results["call-get_order_details"]["id"], "order-1001")
        self.assertEqual(tool_results["call-get_order_details"]["items"][0]["quantity"], 2)
        self.assertEqual(tool_results["call-check_inventory"]["quantity_available"], 20)
        self.assertEqual(tool_results["call-check_inventory"]["location"], "Demo rack A-01")

        for name, arguments in (("delete_order", "{}"), ("check_inventory", '{"product_id":"another-product"}')):
            with self.subTest(name=name, arguments=arguments):
                rejected_client = OpenAI(api_key=config.api_key, base_url=config.base_url, max_retries=0,
                    http_client=httpx.Client(transport=httpx.MockTransport(
                        lambda _request: completion(name=name, arguments=arguments))))
                with self.app.state.sessions() as db:
                    with patch("backend.app.services.investigation.MetaConfig.from_env", return_value=config), \
                         patch("backend.app.services.investigation.create_muse_client", return_value=rejected_client):
                        with self.assertRaisesRegex(ValueError, "invalid_tool_request"):
                            investigate_with_read_tools(db, db.get(Inspection, inspection["id"]), db.get(Order, "order-1001"))
                    self.assertEqual(db.scalar(select(func.count()).select_from(CorrectiveAction)), 1)
                    self.assertEqual(db.scalar(select(func.count()).select_from(Approval)), 0)
                    self.assertEqual(db.get(Order, "order-1001").status, "NEEDS_REVIEW")
                    stock = db.scalar(select(Inventory).where(Inventory.product_id == "product-red"))
                    self.assertEqual(stock.quantity_available, 20)


if __name__ == "__main__":
    unittest.main()
