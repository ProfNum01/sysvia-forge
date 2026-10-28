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


if __name__ == "__main__":
    unittest.main()
