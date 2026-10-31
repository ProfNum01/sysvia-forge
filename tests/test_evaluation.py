import json
import tempfile
import unittest
from pathlib import Path

from evaluation.scripts.run_benchmark import ROOT, metrics, validate_manifest


class EvaluationTests(unittest.TestCase):
    def test_original_synthetic_manifest_is_complete_and_uses_real_files(self):
        document = validate_manifest(ROOT / "evaluation/manifests/synthetic.json")
        self.assertEqual(len(document["cases"]), 5)
        self.assertTrue(all(case["provenance"] == "SYNTHETIC" for case in document["cases"]))

    def test_empty_measurements_do_not_get_percentages(self):
        result = metrics([{"provenance": "SYNTHETIC", "outcome": "NOT_RUN"}])
        self.assertEqual(result["sample_size"], 0)
        self.assertIsNone(result["false_verification_rate_percent"])
        self.assertIsNone(result["valid_action_proposal_rate_percent"])

    def test_fabricated_physical_fixture_label_is_rejected(self):
        original = validate_manifest(ROOT / "evaluation/manifests/synthetic.json")
        original["cases"][0]["provenance"] = "PHYSICAL_CAPTURE"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "manifest.json"
            path.write_text(json.dumps(original), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Synthetic fixture cannot be labeled physical"):
                validate_manifest(path)

    def test_false_verification_is_counted(self):
        result = metrics([{"provenance": "SYNTHETIC", "outcome": "PASS",
                           "inspection_status": "VERIFIED", "expected_discrepancy": ["EXTRA_PRODUCT"]}])
        self.assertEqual(result["false_verification_count"], 1)
        self.assertEqual(result["shipping_safety_violation_count"], 0)

    def test_uncertain_case_is_not_scored_as_missed_detection(self):
        result = metrics([{"provenance": "SYNTHETIC", "outcome": "NEEDS_HUMAN_REVIEW",
                           "inspection_status": "NEEDS_REVIEW", "expected_discrepancy": ["EXTRA_PRODUCT"],
                           "ground_truth_quantities": {"product-green": 1}, "comparison": [
                               {"product_id": "product-green", "observed_quantity": None}]}])
        self.assertEqual(result["uncertain_cases_excluded_from_detection_metrics"], 1)
        self.assertIsNone(result["discrepancy_detection_recall_percent"])
        self.assertIsNone(result["quantity_agreement_percent"])
