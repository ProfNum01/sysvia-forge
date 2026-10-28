from __future__ import annotations

import asyncio
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from PIL import Image

from backend.app.services.perception import build_regions, ground_observations
from backend.app.services.provider import run_visual_models
from proofsight.meta_api import MetaConfig, SegmentationResult


CATALOG = [{"id": "p1", "sku": "SKU-001", "name": "Blue box", "description": "a blue cardboard box"},
           {"id": "p2", "sku": "SKU-002", "name": "Red box", "description": "a red cardboard box"}]
BOX = {"left": 10, "top": 10, "right": 30, "bottom": 30}


def observation(product_id="p1", box=None):
    return {"product_id": product_id, "quantity": 1, "label_text": "SKU-001" if product_id == "p1" else "SKU-002",
            "evidence": "One readable label on the actual scene object", "identity_certain": True,
            "count_certain": True, "source_box": copy.deepcopy(BOX if box is None else box)}


def segmentation(boxes=None, ok=True):
    return {"ok": ok, "model": "sam-3.1", "boxes": boxes if boxes is not None else [{"object_id": "0", **BOX}],
            "masks": [], "diagnostics": [], "annotated_image": None, "latency_ms": 10,
            "http_status": 200 if ok else 429, "error": None if ok else {"category": "rate_limit", "http_status": 429}}


class GroundingTests(unittest.TestCase):
    def test_exact_scene_sku_and_unique_sam_overlap_ground_one_unit(self):
        regions = build_regions([("p1", segmentation())])
        result = ground_observations([observation()], regions, CATALOG)
        self.assertEqual(result[0]["identification_status"], "MATCHED")
        self.assertEqual(result[0]["evidence_region_ids"], ["region-p1-0"])
        self.assertEqual(result[0]["quantity"], 1)
        self.assertEqual(regions[0]["product_id"], "p1")
        self.assertEqual(regions[0]["source"], "sam-3.1")
        self.assertEqual(regions[0]["box"], BOX)

    def test_missing_localization_or_wrong_scene_label_never_matches(self):
        variants = [{**observation(), "source_box": None}, {**observation(), "label_text": "blue packaging"},
                    {**observation(), "quantity": 2}, {**observation(), "identity_certain": False},
                    {**observation(), "source_box": {"left": 70, "top": 70, "right": 90, "bottom": 90}}]
        for row in variants:
            regions = build_regions([("p1", segmentation())])
            result = ground_observations([row], regions, CATALOG)
            self.assertEqual(result[0]["identification_status"], "UNCERTAIN")
            self.assertFalse(result[0]["identity_certain"])
            self.assertFalse(result[0]["count_certain"])
            self.assertIsNone(result[0]["quantity"])
            self.assertEqual(result[0]["evidence_region_ids"], [])
            self.assertIsNone(regions[0]["product_id"])

    def test_two_separate_visible_units_keep_distinct_evidence_regions(self):
        other = {"left": 40, "top": 10, "right": 60, "bottom": 30}
        regions = build_regions([("p1", segmentation([{"object_id": "0", **BOX}, {"object_id": "1", **other}]))])
        result = ground_observations([observation(), observation(box=other)], regions, CATALOG)
        self.assertEqual([row["identification_status"] for row in result], ["MATCHED", "MATCHED"])
        self.assertEqual([row["evidence_region_ids"] for row in result], [["region-p1-0"], ["region-p1-1"]])

    def test_duplicate_model_claims_cannot_count_one_region_twice(self):
        regions = build_regions([("p1", segmentation())])
        result = ground_observations([observation(), observation()], regions, CATALOG)
        self.assertTrue(all(not row["count_certain"] for row in result))
        self.assertIsNone(regions[0]["product_id"])

    def test_overlapping_duplicate_regions_are_deduplicated(self):
        regions = build_regions([("p1", segmentation([{"object_id": "0", **BOX}, {"object_id": "1", **BOX}]))])
        self.assertEqual(len(regions), 1)
        result = ground_observations([observation()], regions, CATALOG)
        self.assertEqual(result[0]["quantity"], 1)

    def test_overlapping_different_product_prompts_do_not_establish_identity(self):
        regions = build_regions([("p1", segmentation()), ("p2", segmentation())])
        self.assertEqual(len(regions), 1)
        self.assertIsNone(regions[0]["candidate_product_id"])
        result = ground_observations([observation()], regions, CATALOG)
        self.assertEqual(result[0]["identification_status"], "UNCERTAIN")
        self.assertIsNone(regions[0]["product_id"])

    def test_ambiguous_multiple_same_product_regions_are_not_assigned_in_order(self):
        overlapping = {"left": 12, "top": 10, "right": 34, "bottom": 30}
        regions = build_regions([("p1", segmentation([{"object_id": "0", **BOX}, {"object_id": "1", **overlapping}]))])
        result = ground_observations([observation()], regions, CATALOG)
        self.assertEqual(result[0]["identification_status"], "UNCERTAIN")

    def test_extra_catalog_product_can_match_without_order_filtering(self):
        regions = build_regions([("p2", segmentation())])
        result = ground_observations([observation("p2")], regions, CATALOG)
        self.assertEqual(result[0]["sku"], "SKU-002")
        self.assertEqual(result[0]["identification_status"], "MATCHED")

    def test_unidentified_geometry_has_no_invented_product(self):
        regions = build_regions([(None, segmentation())])
        row = {**observation(), "product_id": None, "identity_certain": False, "label_text": "unreadable"}
        result = ground_observations([row], regions, CATALOG)
        self.assertEqual(result[0]["identification_status"], "UNIDENTIFIED")
        self.assertIsNone(result[0]["sku"])
        self.assertIsNone(regions[0]["product_id"])


class ProviderBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.image = Path(self.temp.name) / "scene.png"
        Image.new("RGB", (100, 100), "white").save(self.image)
        self.timeline = []

    def run_pipeline(self, observations, fail_second=False, products=None, muse_ok=True):
        def inspect(*args):
            self.timeline.append("actual-muse-call")
            return {"ok": muse_ok, "model": "muse-spark-1.3", "observations": observations,
                    "http_status": 200, "latency_ms": 2, "usage": {"total_tokens": 10}, "error": None}
        async def segment(image_path, prompt, annotation):
            self.timeline.append(("actual-sam-call", prompt, asyncio.get_running_loop()))
            value = segmentation(ok=not (fail_second and "red" in prompt))
            return SegmentationResult(**value, outcome={"status": "completed"})
        async def close():
            self.timeline.append(("sam-close", asyncio.get_running_loop()))
        def event(name, details):
            self.timeline.append(("event", name, details))
        with patch("backend.app.services.provider.MetaConfig.from_env", return_value=MetaConfig(api_key="test-only")), \
             patch("backend.app.services.provider.create_muse_client", return_value=Mock()), \
             patch("backend.app.services.provider.create_sam_client", return_value=Mock(close=AsyncMock(side_effect=close))), \
             patch("backend.app.services.provider.MuseSparkService.inspect_image", side_effect=inspect), \
             patch("backend.app.services.provider.SamSegmentationService.segment", side_effect=segment):
            return run_visual_models(str(self.image), products or CATALOG, self.image.parent / "annotation.png", on_event=event)

    def test_callbacks_describe_real_bounded_operations_and_close_same_loop(self):
        result = self.run_pipeline([observation(), observation("p2")])
        self.assertTrue(result["sam"]["ok"])
        names = [event[1] for event in self.timeline if isinstance(event, tuple) and event[0] == "event"]
        self.assertEqual(names, ["MUSE_ANALYSIS_STARTED", "MUSE_ANALYSIS_COMPLETED", "SAM_SEGMENTATION_STARTED",
                                 "SAM_SEGMENTATION_COMPLETED", "SAM_SEGMENTATION_STARTED", "SAM_SEGMENTATION_COMPLETED"])
        self.assertEqual(self.timeline[0][1], "MUSE_ANALYSIS_STARTED")
        self.assertEqual(self.timeline[1], "actual-muse-call")
        sam_calls = [entry for entry in self.timeline if isinstance(entry, tuple) and entry[0] == "actual-sam-call"]
        self.assertEqual([entry[1] for entry in sam_calls], ["a blue cardboard box", "a red cardboard box"])
        self.assertIs(sam_calls[0][2], self.timeline[-1][1])

    def test_failed_sam_call_makes_aggregate_fail(self):
        result = self.run_pipeline([observation(), observation("p2")], fail_second=True)
        self.assertFalse(result["sam"]["ok"])
        self.assertEqual(result["sam"]["error"]["category"], "rate_limit")
        self.assertTrue(all(not row["count_certain"] for row in result["observations"]))

    def test_no_known_identity_requests_unknown_geometry_without_assigning_product(self):
        result = self.run_pipeline([{**observation(), "product_id": None, "identity_certain": False}])
        self.assertEqual(len(result["regions"]), 1)
        self.assertIsNone(result["regions"][0]["candidate_product_id"])
        self.assertIsNone(result["regions"][0]["product_id"])

    def test_failed_muse_does_not_request_sam(self):
        result = self.run_pipeline([], muse_ok=False)
        self.assertIsNone(result["sam"])
        self.assertEqual(result["regions"], [])
        self.assertFalse(any(isinstance(row, tuple) and row[0] == "actual-sam-call" for row in self.timeline))

    def test_sam_requests_capped_at_four_distinct_catalog_products(self):
        products = [{"id": f"p{i}", "sku": f"SKU-{i}", "name": f"Box {i}", "description": f"cardboard box {i}"} for i in range(6)]
        rows = [{**observation(), "product_id": product["id"], "label_text": product["sku"]} for product in products]
        result = self.run_pipeline(rows, products=products)
        calls = [row for row in self.timeline if isinstance(row, tuple) and row[0] == "actual-sam-call"]
        self.assertEqual(len(calls), 4)
        self.assertFalse(result["sam"]["ok"])
        self.assertEqual(result["sam"]["error"]["category"], "segmentation_budget_exceeded")
