"""Mocked API workflows and local persistence checks; no live inference claims."""
from __future__ import annotations

import copy
import hashlib
import io
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, select

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.models.database import AuditEvent, Discrepancy, Inspection, InspectionObservation
from backend.app.services.seed import seed_demo
from model_fixtures import grounded_visual_result


def synthetic_image(color="white"):
    output = io.BytesIO()
    Image.new("RGB", (32, 32), color).save(output, "PNG")
    return output.getvalue()


class InspectionWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = Settings(data_dir=Path(self.temp.name),
                                 database_url=f"sqlite:///{Path(self.temp.name) / 'workflow.db'}",
                                 operator_token="workflow-test-token")
        self.app = create_app(self.settings)
        self.context = TestClient(self.app)
        self.client = self.context.__enter__()
        with self.app.state.sessions() as db:
            seed_demo(db)
        self.auth = {"Authorization": "Bearer workflow-test-token"}

    def tearDown(self):
        self.context.__exit__(None, None, None)
        self.app.state.engine.dispose()
        self.temp.cleanup()

    def upload(self, *, key=None, color="white", order="order-1001", parent=None):
        headers = dict(self.auth)
        if key:
            headers["Idempotency-Key"] = key
        path = f"/api/inspections/{parent}/reinspect" if parent else "/api/inspections"
        return self.client.post(path, headers=headers, data={"order_id": order, "rights_confirmed": "true"},
                                files={"image": ("synthetic.png", synthetic_image(color), "image/png")})

    def analyze(self, inspection_id, result):
        with patch("backend.app.api.routes.run_visual_models", return_value=result):
            return self.client.post(f"/api/inspections/{inspection_id}/analyze", headers=self.auth)

    def test_upload_idempotency_preserves_photo_and_does_not_duplicate_audits(self):
        original = self.upload(key="upload-original-1234")
        self.assertEqual(original.status_code, 201)
        with self.app.state.sessions() as db:
            count_before = db.scalar(select(func.count()).select_from(AuditEvent))
        replay = self.upload(key="upload-original-1234")
        self.assertEqual(replay.status_code, 201)
        self.assertEqual(replay.json()["id"], original.json()["id"])
        self.assertEqual(replay.json()["photo_id"], original.json()["photo_id"])
        with self.app.state.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(AuditEvent)), count_before)
            self.assertEqual(db.scalar(select(func.count()).select_from(Inspection)), 1)
        self.assertEqual(len(list((self.settings.data_dir / "uploads").glob("*.png"))), 1)

    def test_upload_key_cannot_be_reused_for_changed_image_order_or_parent(self):
        original = self.upload(key="upload-bound-1234").json()
        self.assertEqual(self.upload(key="upload-bound-1234", color="blue").status_code, 409)
        self.assertEqual(self.upload(key="upload-bound-1234", order="order-1002").status_code, 409)
        self.assertEqual(self.upload(key="upload-bound-1234", parent=original["id"]).status_code, 409)
        self.assertEqual(self.analyze(original["id"], grounded_visual_result()).status_code, 200)
        replacement = self.upload(key="reinspect-bound-1234", color="blue", parent=original["id"])
        self.assertEqual(replacement.status_code, 201)
        replay = self.upload(key="reinspect-bound-1234", color="blue", parent=original["id"])
        self.assertEqual(replay.status_code, 201)
        self.assertEqual(replay.json()["id"], replacement.json()["id"])
        self.assertEqual(self.upload(key="reinspect-bound-1234", color="blue").status_code, 409)
        with self.app.state.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Inspection)), 2)

    def test_duplicate_analyze_does_not_make_a_second_model_request(self):
        inspection = self.upload().json()
        requests = []

        def provider(image_path, catalog, annotation_path, on_event=None):
            requests.append((image_path, catalog))
            return grounded_visual_result()

        with patch("backend.app.api.routes.run_visual_models", side_effect=provider):
            first = self.client.post(f"/api/inspections/{inspection['id']}/analyze", headers=self.auth)
            duplicate = self.client.post(f"/api/inspections/{inspection['id']}/analyze", headers=self.auth)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(len(requests), 1)
        self.assertEqual({product["id"] for product in requests[0][1]},
                         {"product-red", "product-blue", "product-amber", "product-green"})

    def test_malformed_observation_and_outside_geometry_leave_no_partial_results(self):
        original = grounded_visual_result()
        malformed = copy.deepcopy(original)
        malformed["observations"][1]["quantity"] = "1"
        outside = copy.deepcopy(original)
        outside["regions"][1]["box"]["right"] = 33
        for name, result in (("malformed-observation", malformed), ("outside-image-region", outside)):
            with self.subTest(name=name):
                # A separate order keeps each failed image independent and current.
                order = "order-1001" if name == "malformed-observation" else "order-1002"
                inspection = self.upload(order=order).json()
                response = self.analyze(inspection["id"], result)
                self.assertEqual(response.status_code, 502)
                saved = self.client.get(f"/api/inspections/{inspection['id']}").json()
                self.assertEqual(saved["status"], "PROVIDER_ERROR")
                self.assertEqual(saved["provider_error_details"]["category"], "invalid_structured_evidence")
                self.assertEqual((saved["observations"], saved["discrepancies"], saved["regions"], saved["comparison"]),
                                 ([], [], [], []))
                with self.app.state.sessions() as db:
                    self.assertEqual(db.scalar(select(func.count()).select_from(InspectionObservation).where(
                        InspectionObservation.inspection_id == inspection["id"])), 0)
                    self.assertEqual(db.scalar(select(func.count()).select_from(Discrepancy).where(
                        Discrepancy.inspection_id == inspection["id"])), 0)

    def test_correct_pipeline_persists_exact_comparison_and_evidence_ids(self):
        inspection = self.upload().json()
        result = grounded_visual_result()
        response = self.analyze(inspection["id"], result)
        self.assertEqual(response.status_code, 200)
        saved = self.client.get(f"/api/inspections/{inspection['id']}/results").json()
        self.assertEqual((saved["status"], saved["reconciliation_status"]), ("VERIFIED", "VERIFIED"))
        rows = {row["product_id"]: row for row in saved["comparison"]}
        self.assertEqual((rows["product-red"]["observed_quantity"], rows["product-red"]["difference"]), (2, 0))
        self.assertEqual((rows["product-blue"]["observed_quantity"], rows["product-blue"]["difference"]), (1, 0))
        self.assertEqual(rows["product-red"]["evidence_region_ids"], ["region-1", "region-2"])
        self.assertEqual({r["id"] for r in saved["regions"]}, {"region-1", "region-2", "region-3"})
        self.assertTrue(all(row["identification_status"] == "MATCHED" for row in saved["observations"]))
        self.assertTrue(all(len(row["evidence_region_ids"]) == 1 for row in saved["observations"]))

    def test_supported_shortfall_and_excess_persist_deterministic_arithmetic(self):
        first = self.upload().json()
        shortfall = self.analyze(first["id"], grounded_visual_result(red_quantity=1))
        self.assertEqual(shortfall.status_code, 200)
        saved = self.client.get(f"/api/inspections/{first['id']}").json()
        self.assertEqual((saved["status"], saved["reconciliation_status"]), ("NEEDS_REVIEW", "MISMATCH_DETECTED"))
        red = next(row for row in saved["comparison"] if row["product_id"] == "product-red")
        self.assertEqual((red["required_quantity"], red["observed_quantity"], red["difference"], red["status"]),
                         (2, 1, -1, "SHORTFALL"))
        newer = self.upload(parent=first["id"], color="blue").json()
        excess = self.analyze(newer["id"], grounded_visual_result(red_quantity=3))
        self.assertEqual(excess.status_code, 200)
        red = next(row for row in excess.json()["comparison"] if row["product_id"] == "product-red")
        self.assertEqual((red["observed_quantity"], red["difference"], red["status"]), (3, 1, "EXCESS"))
        self.assertEqual(excess.json()["reconciliation_status"], "MISMATCH_DETECTED")

    def test_unobserved_product_remains_unknown_in_persisted_comparison(self):
        result = grounded_visual_result()
        result["observations"] = result["observations"][:2]
        result["regions"] = result["regions"][:2]
        inspection = self.upload().json()
        response = self.analyze(inspection["id"], result)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "NEEDS_REVIEW")
        blue = next(row for row in response.json()["comparison"] if row["product_id"] == "product-blue")
        self.assertEqual(blue["status"], "NOT_OBSERVED")
        self.assertIsNone(blue["observed_quantity"])
        self.assertIsNone(blue["difference"])

    def test_unexpected_catalog_product_is_persisted_as_extra_product(self):
        result = grounded_visual_result()
        result["regions"].append({"id": "amber-extra", "object_id": "amber", "source": "sam-3.1",
            "box": {"left": 25, "top": 1, "right": 31, "bottom": 7},
            "candidate_product_id": "product-amber", "product_id": "product-amber", "mask": None})
        result["observations"].append({"product_id": "product-amber", "sku": "PS-AMBER-03", "quantity": 1,
            "label_text": "PS-AMBER-03", "evidence": "Mock fixture: separately visible labelled amber unit.",
            "identity_certain": True, "count_certain": True, "identification_status": "MATCHED",
            "evidence_region_ids": ["amber-extra"]})
        inspection = self.upload().json()
        response = self.analyze(inspection["id"], result)
        self.assertEqual(response.status_code, 200)
        saved = self.client.get(f"/api/inspections/{inspection['id']}").json()
        self.assertEqual((saved["status"], saved["reconciliation_status"]), ("NEEDS_REVIEW", "MISMATCH_DETECTED"))
        amber = next(row for row in saved["comparison"] if row["product_id"] == "product-amber")
        self.assertEqual((amber["required_quantity"], amber["observed_quantity"], amber["difference"], amber["status"]),
                         (0, 1, 1, "EXTRA_PRODUCT"))
        self.assertEqual(amber["evidence_region_ids"], ["amber-extra"])

    def test_unidentified_observation_and_unclaimed_region_cannot_verify(self):
        for include_observation in (True, False):
            with self.subTest(include_observation=include_observation):
                result = grounded_visual_result()
                result["regions"].append({"id": "unknown-unit", "object_id": "unknown", "source": "sam-3.1",
                    "box": {"left": 25, "top": 25, "right": 31, "bottom": 31},
                    "candidate_product_id": None, "product_id": None, "mask": None})
                if include_observation:
                    result["observations"].append({"product_id": None, "sku": None, "quantity": None,
                        "label_text": "", "evidence": "Mock fixture: unknown object separately localized.",
                        "identity_certain": False, "count_certain": False, "identification_status": "UNIDENTIFIED",
                        "evidence_region_ids": ["unknown-unit"]})
                order = "order-1001" if include_observation else "order-1002"
                # Align the second test's order quantities with the exact fixture, so unknown evidence is decisive.
                if not include_observation:
                    from backend.app.models.database import OrderItem
                    with self.app.state.sessions() as db:
                        for line in db.scalars(select(OrderItem).where(OrderItem.order_id == order)):
                            if line.product_id == "product-amber":
                                line.product_id, line.quantity = "product-red", 2
                            else:
                                line.product_id, line.quantity = "product-blue", 1
                        db.commit()
                inspection = self.upload(order=order).json()
                response = self.analyze(inspection["id"], result)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["status"], "NEEDS_REVIEW")
                self.assertEqual(response.json()["reconciliation_status"], "NEEDS_REVIEW")
                self.assertTrue(response.json()["discrepancies"])

    def test_progress_events_are_pollable_during_provider_operation(self):
        inspection = self.upload().json()
        entered, release = threading.Event(), threading.Event()

        def provider(_path, _catalog, _annotation, on_event=None):
            on_event("MUSE_ANALYSIS_STARTED", {"model": "muse-spark-1.3"})
            entered.set()
            if not release.wait(10):
                raise RuntimeError("Test barrier timed out")
            on_event("MUSE_ANALYSIS_COMPLETED", {"model": "muse-spark-1.3", "ok": True, "http_status": 200})
            on_event("SAM_SEGMENTATION_STARTED", {"model": "sam-3.1", "product_id": "product-red"})
            on_event("SAM_SEGMENTATION_COMPLETED", {"model": "sam-3.1", "ok": True, "http_status": 200})
            return grounded_visual_result()

        with patch("backend.app.api.routes.run_visual_models", side_effect=provider):
            with ThreadPoolExecutor(max_workers=1) as executor:
                pending = executor.submit(self.client.post, f"/api/inspections/{inspection['id']}/analyze", headers=self.auth)
                try:
                    self.assertTrue(entered.wait(10))
                    progress = self.client.get(f"/api/inspections/{inspection['id']}").json()
                    self.assertEqual((progress["status"], progress["processing_stage"]), ("ANALYZING", "MUSE_ANALYSIS_STARTED"))
                    events = [event["event_type"] for event in progress["execution_events"]]
                    self.assertIn("MUSE_ANALYSIS_STARTED", events)
                    self.assertNotIn("SAM_SEGMENTATION_STARTED", events)
                    self.assertEqual(progress["observations"], [])
                finally:
                    release.set()
                response = pending.result(timeout=10)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["processing_stage"], "RECONCILIATION_COMPLETED")
        events = [event["event_type"] for event in response.json()["execution_events"]]
        for stage in ("MUSE_ANALYSIS_COMPLETED", "SAM_SEGMENTATION_STARTED", "SAM_SEGMENTATION_COMPLETED", "RECONCILIATION_COMPLETED"):
            self.assertIn(stage, events)

    def test_provider_auth_and_rate_limit_errors_are_persisted_without_fake_sam_events(self):
        for status, category, retryable in ((401, "authentication", False), (429, "rate_limit", True)):
            with self.subTest(status=status):
                inspection = self.upload(order="order-1001" if status == 401 else "order-1002").json()

                def failed_provider(_path, _catalog, _annotation, on_event=None):
                    on_event("MUSE_ANALYSIS_STARTED", {"model": "muse-spark-1.3"})
                    on_event("MUSE_ANALYSIS_COMPLETED", {"model": "muse-spark-1.3", "ok": False, "http_status": status})
                    return {"muse": {"ok": False, "error": {"category": category, "http_status": status}},
                            "sam": None, "observations": [], "regions": []}

                with patch("backend.app.api.routes.run_visual_models", side_effect=failed_provider):
                    response = self.client.post(f"/api/inspections/{inspection['id']}/analyze", headers=self.auth)
                self.assertEqual(response.status_code, 429 if status == 429 else 502)
                saved = self.client.get(f"/api/inspections/{inspection['id']}").json()
                self.assertEqual(saved["status"], "PROVIDER_ERROR")
                self.assertEqual(saved["provider_error_details"], {"category": category, "http_status": status, "retryable": retryable})
                self.assertFalse(any(event["event_type"].startswith("SAM_") for event in saved["execution_events"]))
                self.assertEqual(saved["observations"], [])
                recovered = self.analyze(inspection["id"], grounded_visual_result())
                self.assertEqual(recovered.status_code, 200)
                self.assertIsNone(recovered.json()["provider_error_details"])
                self.assertEqual(recovered.json()["photo_id"], inspection["photo_id"])

    def test_additive_sqlite_upgrade_preserves_legacy_evidence_and_observations(self):
        legacy_dir = self.settings.data_dir / "legacy"
        (legacy_dir / "uploads").mkdir(parents=True)
        photo_id = str(uuid4())
        image = synthetic_image("green")
        original_path = legacy_dir / "uploads" / f"{photo_id}.png"
        original_path.write_bytes(image)
        legacy_db = legacy_dir / "old.db"
        with closing(sqlite3.connect(legacy_db)) as db, db:
            db.executescript("""
                CREATE TABLE inspections (id VARCHAR PRIMARY KEY, order_id VARCHAR NOT NULL, status VARCHAR NOT NULL,
                    photo_id VARCHAR UNIQUE NOT NULL, image_path VARCHAR NOT NULL, image_sha256 VARCHAR NOT NULL,
                    previous_inspection_id VARCHAR, resolved_by_inspection_id VARCHAR, provider_error TEXT,
                    investigation TEXT, segmentations JSON NOT NULL, provider_metadata JSON NOT NULL, created_at VARCHAR NOT NULL);
                CREATE TABLE inspection_observations (id VARCHAR PRIMARY KEY, inspection_id VARCHAR NOT NULL,
                    product_id VARCHAR, quantity INTEGER, label_text TEXT NOT NULL, evidence TEXT NOT NULL,
                    identity_certain BOOLEAN NOT NULL, count_certain BOOLEAN NOT NULL);
            """)
            db.execute("INSERT INTO inspections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       ("legacy-inspection", "order-1001", "NEEDS_REVIEW", photo_id, str(original_path),
                        hashlib.sha256(image).hexdigest(), None, None, None, "Original retained investigation", "[]", "{}", "2026-10-28T12:00:00Z"))
            db.execute("INSERT INTO inspection_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       ("legacy-observation", "legacy-inspection", None, None, "Unreadable", "Original ambiguous evidence", False, False))
        settings = Settings(data_dir=legacy_dir, database_url=f"sqlite:///{legacy_db}", operator_token="legacy-test-token")
        upgraded_app = create_app(settings)
        with TestClient(upgraded_app) as client:
            with upgraded_app.state.sessions() as db:
                seed_demo(db)
            response = client.get("/api/inspections/legacy-inspection")
            self.assertEqual(response.status_code, 200)
            saved = response.json()
            self.assertEqual(saved["photo_id"], photo_id)
            self.assertEqual(saved["investigation"], "Original retained investigation")
            self.assertEqual(saved["observations"][0]["evidence"], "Original ambiguous evidence")
            self.assertEqual(saved["observations"][0]["identification_status"], "UNCERTAIN")
            self.assertEqual(saved["observations"][0]["evidence_region_ids"], [])
            self.assertEqual((saved["image_width"], saved["image_height"]), (32, 32))
            self.assertEqual(client.get(saved["image_url"]).content, image)
            self.assertEqual(original_path.read_bytes(), image)
        # The additive upgrade is repeatable and cannot discard retained evidence.
        with TestClient(create_app(settings)) as client:
            self.assertEqual(client.get("/api/inspections/legacy-inspection").json()["photo_id"], photo_id)


if __name__ == "__main__":
    unittest.main()
