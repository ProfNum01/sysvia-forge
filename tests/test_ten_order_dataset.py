import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evaluation/datasets/ten-orders"


def test_ten_order_dataset_is_complete():
    index = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    cases = index["cases"]
    assert len(cases) == 10
    assert len({case["order_id"] for case in cases}) == 10
    assert sum(case["expected_discrepancy"] == [] for case in cases) == 6
    assert sum(bool(case["expected_discrepancy"]) for case in cases) == 4
    assert len({case["scenario_id"] for case in cases}) == 10
    for case in cases:
        order = json.loads((DATA / "orders" / f'{case["order_id"]}.json').read_text(encoding="utf-8"))
        assert order["items"] == case["expected_quantities"]
        assert order["image"] == case["evidence"]
        with Image.open(ROOT / case["evidence"]) as image:
            assert image.size == (1200, 900)
            image.verify()
        assert (case["expected_quantities"] == case["ground_truth_quantities"]) == (case["expected_discrepancy"] == [])
