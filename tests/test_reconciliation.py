"""Deterministic fixtures only: no live inference and no warehouse accuracy claims."""
import unittest
from backend.app.services.reconciliation import reconcile


CATALOG = [{"id": "red", "sku": "RED-1", "name": "Red"}, {"id": "blue", "sku": "BLUE-1", "name": "Blue"}]
EXPECTED = [{"product_id": "red", "sku": "RED-1", "name": "Red", "quantity": 2}]


def observations(product="red", count=1):
    sku = "RED-1" if product == "red" else "BLUE-1"
    return [{"product_id": product, "quantity": 1, "label_text": sku, "evidence": "Readable scene label on a distinct unit.",
             "identity_certain": True, "count_certain": True, "evidence_region_ids": [f"{product}-{n}"]}
            for n in range(count)]


def regions(product="red", count=1):
    top = 20 if product == "blue" else 0
    return [{"id": f"{product}-{n}", "product_id": product, "box": {"left": n*20, "top": top, "right": n*20+10, "bottom": top+10}}
            for n in range(count)]


class ReconciliationTests(unittest.TestCase):
    def run_reconcile(self, obs, evidence):
        return reconcile(EXPECTED, obs, True, catalog=CATALOG, regions=evidence)

    def test_supported_shortfall_uses_python_arithmetic(self):
        result = self.run_reconcile(observations(), regions())
        row = result["comparison"][0]
        self.assertEqual((row["required_quantity"], row["observed_quantity"], row["difference"]), (2, 1, -1))
        self.assertEqual(result["reconciliation_status"], "MISMATCH_DETECTED")
        self.assertFalse(result["verified"])

    def test_unconfirmed_candidate_for_required_product_prevents_shortfall_claim(self):
        evidence = regions()
        evidence.append({"id": "red-1", "product_id": None, "candidate_product_id": "red",
                         "box": {"left": 20, "top": 0, "right": 30, "bottom": 10}})
        result = self.run_reconcile(observations(), evidence)
        row = result["comparison"][0]
        self.assertEqual(row["status"], "UNCERTAIN")
        self.assertIsNone(row["observed_quantity"])
        self.assertIsNone(row["difference"])
        self.assertEqual(result["reconciliation_status"], "NEEDS_REVIEW")

    def test_distinct_supported_units_can_verify(self):
        result = self.run_reconcile(observations(count=2), regions(count=2))
        self.assertTrue(result["verified"])
        self.assertEqual(result["comparison"][0]["difference"], 0)

    def test_excess_and_unexpected_catalog_product(self):
        result = self.run_reconcile(observations(count=3)+observations("blue"), regions(count=3)+regions("blue"))
        self.assertEqual({d["type"] for d in result["discrepancies"]}, {"EXCESS", "EXTRA_PRODUCT"})
        extra = result["comparison"][1]
        self.assertEqual((extra["required_quantity"], extra["observed_quantity"], extra["difference"]), (0, 1, 1))

    def test_not_observed_is_unknown_not_zero(self):
        result = self.run_reconcile([], [])
        row = result["comparison"][0]
        self.assertIsNone(row["observed_quantity"])
        self.assertIsNone(row["difference"])
        self.assertEqual(result["reconciliation_status"], "NEEDS_REVIEW")

    def test_unidentified_object_requires_review(self):
        result = self.run_reconcile([{"product_id": None, "quantity": None, "label_text": "", "evidence": "Unreadable item.",
                                     "identity_certain": False, "count_certain": False, "evidence_region_ids": []}], [])
        self.assertEqual(result["observations"][0]["identification_status"], "UNIDENTIFIED")
        self.assertFalse(result["verified"])

    def test_missing_or_wrong_region_cannot_support_count(self):
        for evidence in [[], regions("blue")]:
            with self.subTest(evidence=evidence):
                result = self.run_reconcile(observations(), evidence)
                self.assertIsNone(result["comparison"][0]["observed_quantity"])
                self.assertEqual(result["observations"][0]["identification_status"], "UNCERTAIN")

    def test_duplicate_region_never_double_counts(self):
        obs = observations()
        result = self.run_reconcile(obs+obs, regions())
        self.assertIsNone(result["comparison"][0]["observed_quantity"])
        self.assertFalse(result["verified"])

    def test_overlapping_regions_cannot_manufacture_two_units(self):
        evidence = regions(count=2)
        evidence[1]["box"] = evidence[0]["box"].copy()
        result = self.run_reconcile(observations(count=2), evidence)
        self.assertIsNone(result["comparison"][0]["observed_quantity"])

    def test_near_match_sku_and_uncertain_count_never_verify(self):
        for field, value in [("label_text", "RED-10"), ("count_certain", False), ("quantity", 0)]:
            obs = observations(count=2)
            obs[0][field] = value
            result = self.run_reconcile(obs, regions(count=2))
            self.assertFalse(result["verified"])
            self.assertIsNone(result["comparison"][0]["observed_quantity"])

    def test_known_wrong_product_is_extra_and_required_product_remains_unobserved(self):
        result = self.run_reconcile(observations("blue"), regions("blue"))
        self.assertEqual({d["type"] for d in result["discrepancies"]}, {"NOT_OBSERVED", "EXTRA_PRODUCT"})
        self.assertIsNone(result["comparison"][0]["difference"])


# --------------------------------------------------------------------------
# No-SKU-label visual matching (packing-scene products without readable labels)
# --------------------------------------------------------------------------
NO_SKU_CATALOG = [
    {"id": "packing-blue-box", "sku": "PACK-BLUE-BOX", "name": "Blue box",
     "description": "blue rectangular box; no visible SKU label", "no_sku_label": True},
    {"id": "packing-red-can", "sku": "PACK-RED-CAN", "name": "Red can",
     "description": "red cylinder; no visible SKU label", "no_sku_label": True},
]
NO_SKU_EXPECTED = [
    {"product_id": "packing-blue-box", "sku": "PACK-BLUE-BOX", "name": "Blue box", "quantity": 2},
    {"product_id": "packing-red-can", "sku": "PACK-RED-CAN", "name": "Red can", "quantity": 1},
]


def _no_sku_regions():
    return [
        {"id": "r-blue-1", "product_id": "packing-blue-box", "candidate_product_id": "packing-blue-box",
         "box": {"left": 0, "top": 0, "right": 100, "bottom": 100}},
        {"id": "r-blue-2", "product_id": "packing-blue-box", "candidate_product_id": "packing-blue-box",
         "box": {"left": 110, "top": 0, "right": 210, "bottom": 100}},
        {"id": "r-red-1", "product_id": "packing-red-can", "candidate_product_id": "packing-red-can",
         "box": {"left": 220, "top": 0, "right": 320, "bottom": 100}},
    ]


def _no_sku_observations(blue_count=2, red_count=1):
    obs = []
    for i in range(blue_count):
        obs.append({
            "product_id": "packing-blue-box", "quantity": 1, "label_text": "",
            "evidence": "[visual-only] Blue box visible", "identity_certain": True, "count_certain": True,
            "visual_candidate_product_id": "packing-blue-box", "visual_evidence": "Blue rectangular shape",
            "evidence_region_ids": [f"r-blue-{i+1}"],
        })
    for i in range(red_count):
        obs.append({
            "product_id": "packing-red-can", "quantity": 1, "label_text": "",
            "evidence": "[visual-only] Red can visible", "identity_certain": True, "count_certain": True,
            "visual_candidate_product_id": "packing-red-can", "visual_evidence": "Red cylinder shape",
            "evidence_region_ids": ["r-red-1"],
        })
    return obs


class NoSKULabelReconciliationTests(unittest.TestCase):
    """Packing-scene products have no visible SKU label; identity uses visual candidate matching."""

    def _run(self, obs, regs=None):
        return reconcile(NO_SKU_EXPECTED, obs, geometry_available=True,
                         catalog=NO_SKU_CATALOG, regions=regs or _no_sku_regions())

    def test_visual_candidate_match_with_sam_geometry_verifies(self):
        """Full correct packing scene: 2 blue boxes + 1 red can -> VERIFIED."""
        result = self._run(_no_sku_observations(blue_count=2, red_count=1))
        self.assertTrue(result["verified"], msg=str(result["discrepancies"]))
        self.assertEqual(result["reconciliation_status"], "VERIFIED")

    def test_missing_visual_evidence_text_does_not_verify(self):
        """Empty visual_evidence means no corroborating description -> observation is UNCERTAIN."""
        obs = _no_sku_observations(blue_count=2, red_count=1)
        obs[0]["visual_evidence"] = ""  # strip visual evidence for first blue box
        result = self._run(obs)
        # Without visual_evidence the observation cannot be MATCHED -> verification fails
        self.assertFalse(result["verified"])

    def test_standard_product_without_no_sku_flag_still_requires_label(self):
        """A product NOT flagged as no_sku_label must still have label_text == SKU."""
        standard_catalog = [{"id": "product-red", "sku": "PS-RED-01", "name": "Red",
                              "description": "a red canister with visible SKU label"}]
        standard_expected = [{"product_id": "product-red", "sku": "PS-RED-01", "name": "Red", "quantity": 1}]
        standard_regions = [{"id": "r1", "product_id": "product-red", "candidate_product_id": "product-red",
                              "box": {"left": 0, "top": 0, "right": 100, "bottom": 100}}]
        # Observation with visual candidate but no label -> must NOT verify (needs real label)
        obs_no_label = [{"product_id": "product-red", "quantity": 1, "label_text": "",
                          "evidence": "Red canister visible", "identity_certain": True, "count_certain": True,
                          "visual_candidate_product_id": "product-red", "visual_evidence": "Red canister",
                          "evidence_region_ids": ["r1"]}]
        result = reconcile(standard_expected, obs_no_label, geometry_available=True,
                           catalog=standard_catalog, regions=standard_regions)
        self.assertFalse(result["verified"],
                         msg="Products with visible SKU labels must not verify via visual-only path")

    def test_no_sku_shortfall_produces_mismatch(self):
        """Only 1 blue box instead of 2 -> MISMATCH_DETECTED."""
        regs = _no_sku_regions()
        # Remove second blue region
        regs_short = [r for r in regs if r["id"] != "r-blue-2"]
        obs_short = _no_sku_observations(blue_count=1, red_count=1)
        result = self._run(obs_short, regs_short)
        self.assertFalse(result["verified"])
        discrepancy_types = {d["type"] for d in result["discrepancies"]}
        self.assertIn("NOT_OBSERVED", discrepancy_types | {"SHORTFALL", "MISMATCH_DETECTED",
                                                            "NOT_OBSERVED", "UNCERTAIN"})


if __name__ == "__main__":
    unittest.main()

