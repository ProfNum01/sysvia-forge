from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import patch

import httpx
from openai import OpenAI
from sqlalchemy import func, select

from backend.app.models.database import (Base, CorrectiveAction, Discrepancy, Inspection, InspectionObservation,
                                        Inventory, Order, connect_database)
from backend.app.services.investigation import investigate_with_read_tools
from backend.app.services.seed import seed_demo
from proofsight.meta_api import MetaConfig


class AgentInvestigationTests(unittest.TestCase):
    """Real SQLite + SDK transport; only external Meta responses are mocked."""

    def setUp(self):
        self.engine, self.sessions = connect_database("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = self.sessions()
        seed_demo(self.db)
        self.order = self.db.get(Order, "order-1001")
        self.inspection = Inspection(id="ins-1", order_id=self.order.id, status="NEEDS_REVIEW", photo_id="photo-1",
            image_path="synthetic-test-fixture.png", image_sha256="fixture-only", reconciliation_status="MISMATCH_DETECTED",
            regions=[{"id": "red-0", "product_id": "product-red", "source": "sam-3.1", "box": {"left": 0,"top": 0,"right": 10,"bottom": 10}},
                     {"id": "blue-0", "product_id": "product-blue", "source": "sam-3.1", "box": {"left": 20,"top": 0,"right": 30,"bottom": 10}}])
        self.db.add(self.inspection)
        self.db.flush()
        self.db.add_all([InspectionObservation(id="obs-red", inspection_id="ins-1", product_id="product-red", quantity=1,
            label_text="PS-RED-01", sku="PS-RED-01", evidence="Synthetic test readable label", identity_certain=True,
            count_certain=True, identification_status="MATCHED", evidence_region_ids=["red-0"]),
            InspectionObservation(id="obs-blue", inspection_id="ins-1", product_id="product-blue", quantity=1,
            label_text="PS-BLUE-02", sku="PS-BLUE-02", evidence="Synthetic test readable label", identity_certain=True,
            count_certain=True, identification_status="MATCHED", evidence_region_ids=["blue-0"]),
            Discrepancy(id="disc-red", inspection_id="ins-1", product_id="product-red", type="SHORTFALL",
                required_quantity=2, observed_quantity=1, status="OPEN", description="Supported visible shortfall fixture")])
        self.order.latest_inspection_id = "ins-1"
        self.order.status = "NEEDS_REVIEW"
        self.db.commit()
        self.requests = []
        self.events = []

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def decision(self, picking=False):
        refs = ["order:order-1001", "inspection:ins-1", "photo:photo-1", "discrepancy:disc-red", "region:red-0"]
        actions = [{"type": "ESCALATE_TO_HUMAN", "product_id": None, "quantity": None,
                    "requires_approval": True, "evidence_references": ["inspection:ins-1"]}]
        if picking:
            refs.append("inventory:product-red")
            actions = [{"type": "CREATE_PICKING_TASK", "product_id": "product-red", "quantity": 1,
                        "requires_approval": True, "evidence_references": ["discrepancy:disc-red", "inventory:product-red", "region:red-0"]}]
        return {"summary": "Evidence-supported visible shortfall; physical correction remains unverified.",
            "recommendation": "CREATE_PICKING_TASK" if picking else "REQUEST_REVIEW",
            "decision": "CORRECTIVE_ACTION_REQUIRED" if picking else "HUMAN_REVIEW_REQUIRED",
            "findings": [{"type": "SHORTFALL", "product_id": "product-red", "quantity": 1,
                          "evidence_references": ["discrepancy:disc-red", "region:red-0"]}],
            "recommended_actions": actions, "evidence_references": refs, "verification_required": True}

    def run_agent(self, decision=None, batches=None, status=200, transport_error=None):
        decision = self.decision() if decision is None else decision
        batches = [[("get_inspection_results", {"inspection_id": "ins-1"}),
                    ("get_order_details", {"order_id": "order-1001"})]] if batches is None else batches
        index = 0
        def respond(request):
            nonlocal index
            payload = json.loads(request.content)
            self.requests.append(payload)
            if transport_error:
                raise transport_error
            if status != 200:
                return httpx.Response(status, json={"error": {"message": "sensitive provider text"}})
            if "response_format" in payload:
                message = {"role": "assistant", "content": json.dumps(decision)}
                finish = "stop"
            elif index < len(batches):
                message = {"role": "assistant", "content": None, "tool_calls": [
                    {"id": f"call-{index}-{ordinal}", "type": "function", "function": {"name": name,
                     "arguments": json.dumps(arguments)}} for ordinal, (name, arguments) in enumerate(batches[index])]}
                index += 1
                finish = "tool_calls"
            else:
                message = {"role": "assistant", "content": "Ready for a structured recommendation."}
                finish = "stop"
            return httpx.Response(200, json={"id": "mock-test-completion", "created": 0, "object": "chat.completion",
                "model": "muse-spark-1.3", "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}})
        client = OpenAI(api_key="test-secret", base_url="https://api.meta.ai/v1", max_retries=0,
                        http_client=httpx.Client(transport=httpx.MockTransport(respond)))
        with patch("backend.app.services.investigation.MetaConfig.from_env", return_value=MetaConfig(api_key="test-secret")), \
             patch("backend.app.services.investigation.create_muse_client", return_value=client):
            return investigate_with_read_tools(self.db, self.inspection, self.order,
                on_event=lambda name, details: self.events.append((name, details)))

    def all_reads(self):
        return [[("get_order_history", {"order_id": "order-1001"}),
                 ("get_pending_actions", {"order_id": "order-1001"}),
                 ("check_inventory", {"product_id": "product-red"}),
                 ("get_inspection_results", {"inspection_id": "ins-1"}),
                 ("get_order_details", {"order_id": "order-1001"})]]

    def test_dynamic_five_tools_return_database_evidence_without_mutations(self):
        result = self.run_agent(self.decision(picking=True), self.all_reads())
        self.assertEqual(result.recommended_actions[0].quantity, 1)
        self.assertEqual({tool["function"]["name"] for tool in self.requests[0]["tools"]},
            {"get_order_details", "get_inspection_results", "check_inventory", "get_pending_actions", "get_order_history"})
        self.assertEqual(self.requests[0]["tool_choice"], "auto")
        returned = [json.loads(message["content"]) for message in self.requests[-1]["messages"] if message["role"] == "tool"]
        inventory = next(value for value in returned if "quantity_available" in value)
        self.assertEqual(inventory["quantity_available"], 20)
        self.assertEqual(inventory["quantity_reserved"], 0)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(CorrectiveAction)), 0)
        self.assertEqual(self.order.status, "NEEDS_REVIEW")
        completed = [details for name, details in self.events if name == "AGENT_MODEL_COMPLETED"]
        self.assertEqual(len(completed), len(self.requests))
        self.assertTrue(all(value["http_status"] == 200 and value["usage"]["total_tokens"] == 30 for value in completed))
        self.assertNotIn("test-secret", json.dumps(self.events))

    def test_unneeded_inventory_and_history_tools_are_not_forced(self):
        result = self.run_agent()
        self.assertEqual(result.decision, "HUMAN_REVIEW_REQUIRED")
        names = [details["tool"] for name, details in self.events if name == "TOOL_CALLED"]
        self.assertEqual(names, ["get_inspection_results", "get_order_details"])

    def test_invalid_tool_arguments_and_cross_order_access_fail_closed(self):
        bad = [("delete_order", {}), ("get_order_details", {"order_id": "order-1002"}),
               ("get_inspection_results", {"inspection_id": "other-inspection"}),
               ("check_inventory", {"product_id": "product-amber"}),
               ("get_order_details", {"order_id": "order-1001", "sql": "DROP TABLE orders"}),
               ("check_inventory", {"product_id": 123})]
        for name, arguments in bad:
            with self.subTest(name=name, arguments=arguments):
                with self.assertRaisesRegex(ValueError, "invalid_tool_request"):
                    self.run_agent(batches=[[(name, arguments)]])
        self.assertEqual(self.db.scalar(select(func.count()).select_from(CorrectiveAction)), 0)

    def test_unknown_product_quantity_permissions_and_evidence_are_rejected(self):
        variants = []
        for key, value in [("product_id", "invented-product"), ("quantity", 2), ("requires_approval", False),
                           ("evidence_references", ["discrepancy:invented"])]:
            decision = self.decision(picking=True)
            decision["recommended_actions"][0][key] = value
            variants.append(decision)
        decision = self.decision(picking=True)
        decision["findings"][0]["quantity"] = 2
        variants.append(decision)
        for decision in variants:
            with self.subTest(decision=decision):
                with self.assertRaises(ValueError):
                    self.run_agent(decision, self.all_reads())

    def test_not_observed_never_allows_model_to_manufacture_picking(self):
        discrepancy = self.db.get(Discrepancy, "disc-red")
        discrepancy.type = "NOT_OBSERVED"
        discrepancy.observed_quantity = None
        self.db.commit()
        with self.assertRaises(ValueError):
            self.run_agent(self.decision(picking=True), self.all_reads())

    def test_insufficient_stock_blocks_picking(self):
        self.db.scalar(select(Inventory).where(Inventory.product_id == "product-red")).quantity_available = 0
        self.db.commit()
        with self.assertRaisesRegex(ValueError, "unsupported_action"):
            self.run_agent(self.decision(picking=True), self.all_reads())

    def test_duplicate_tool_calls_and_oversized_outputs_are_bounded(self):
        repeated = [[("get_order_details", {"order_id": "order-1001"})]] * 2
        with self.assertRaisesRegex(ValueError, "invalid_tool_request"):
            self.run_agent(batches=repeated)
        with patch("backend.app.services.investigation.MAX_TOOL_OUTPUT_BYTES", 20, create=True):
            with self.assertRaisesRegex(ValueError, "tool_output_limit"):
                self.run_agent()

    def test_timeout_and_provider_failure_are_sanitized(self):
        with patch("backend.app.services.investigation.MAX_AGENT_SECONDS", 0, create=True):
            with self.assertRaisesRegex(TimeoutError, "agent_timeout"):
                self.run_agent()
        with self.assertRaises(Exception) as caught:
            self.run_agent(status=401)
        self.assertNotIn("sensitive provider text", str(caught.exception))
        self.assertNotIn("test-secret", str(caught.exception))

    def test_verified_order_can_return_no_actions(self):
        self.db.delete(self.db.get(Discrepancy, "disc-red"))
        self.inspection.status = "VERIFIED"
        self.inspection.reconciliation_status = "VERIFIED"
        self.order.status = "VERIFIED"
        self.db.commit()
        result = self.run_agent({"summary": "Existing verified inspection has no open discrepancy.",
            "recommendation": "REQUEST_REVIEW", "decision": "NO_ACTION_REQUIRED", "findings": [],
            "recommended_actions": [], "evidence_references": ["order:order-1001", "inspection:ins-1"],
            "verification_required": True})
        self.assertEqual(result.recommended_actions, [])

    def test_sdk_timeout_preserves_safe_category_and_request_timeout(self):
        with self.assertRaises(Exception) as caught:
            self.run_agent(transport_error=httpx.ReadTimeout("sensitive transport message"))
        self.assertEqual(caught.exception.safe_error, {"category": "timeout", "http_status": None})
        self.assertNotIn("sensitive transport message", str(caught.exception))
        self.assertEqual(self.events[-1][1]["error"]["category"], "timeout")

    def test_readable_sku_token_in_longer_label_supports_picking(self):
        row = self.db.get(InspectionObservation, "obs-red")
        row.label_text = "SKU: PS-RED-01 / batch ABC"
        self.db.commit()
        result = self.run_agent(self.decision(picking=True), self.all_reads())
        self.assertEqual(result.recommended_actions[0].quantity, 1)

    def test_five_dynamic_tool_rounds_still_leave_one_final_request(self):
        batches = [[call] for call in self.all_reads()[0]]
        result = self.run_agent(self.decision(picking=True), batches)
        self.assertEqual(len(self.requests), 6)
        self.assertEqual(result.decision, "CORRECTIVE_ACTION_REQUIRED")

    def test_individual_tool_runtime_is_bounded(self):
        with patch("backend.app.services.investigation.MAX_TOOL_SECONDS", 0):
            with self.assertRaisesRegex(TimeoutError, "agent_timeout"):
                self.run_agent()

    def test_policy_rejection_emits_allowlisted_reason_and_safe_machine_candidate(self):
        decision = self.decision(picking=True)
        decision["summary"] = "sensitive-provider-or-model-prose"
        decision["recommended_actions"][0]["product_id"] = "sensitive-unknown-product"
        with self.assertRaises(ValueError) as caught:
            self.run_agent(decision, self.all_reads())
        self.assertEqual(caught.exception.safe_reason, "unsupported_action")
        event = next(details for name, details in self.events if name == "VALIDATION_FAILED")
        self.assertEqual(event["validation_stage"], "policy")
        self.assertEqual(event["candidate"]["recommended_actions"][0]["product_id"], "UNSUPPORTED_PRODUCT")
        self.assertNotIn("sensitive", json.dumps(event))

    def test_schema_rejection_emits_safe_diagnostic_without_raw_model_text(self):
        decision = self.decision()
        decision["findings"][0]["quantity"] = 0
        decision["summary"] = "sensitive-freeform-text"
        with self.assertRaises(ValueError) as caught:
            self.run_agent(decision)
        self.assertEqual(caught.exception.safe_reason, "invalid_agent_decision")
        event = next(details for name, details in self.events if name == "VALIDATION_FAILED")
        self.assertEqual(event["validation_stage"], "schema")
        self.assertEqual(event["candidate"]["findings"][0]["quantity"], 0)
        self.assertNotIn("sensitive-freeform-text", json.dumps(event))

    def test_held_order_is_an_actual_operational_constraint_with_null_quantity(self):
        self.order.status = "HELD"
        self.db.commit()
        decision = self.decision()
        decision["findings"].append({"type": "OPERATIONAL_CONSTRAINT", "product_id": None, "quantity": None,
            "evidence_references": ["order:order-1001"]})
        result = self.run_agent(decision)
        self.assertEqual(result.findings[-1].type, "OPERATIONAL_CONSTRAINT")
        self.order.status = "NEEDS_REVIEW"
        self.db.commit()
        with self.assertRaises(ValueError):
            self.run_agent(decision)
