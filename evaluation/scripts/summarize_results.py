"""Combine existing live benchmark records without making new model requests."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from evaluation.scripts.run_benchmark import failure_analysis, metrics


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "data/evaluation-results/summary.json")
    args = parser.parse_args(argv)
    rows = []
    for path in args.results:
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("mode") != "LIVE_META":
            parser.error("Summary accepts only actual live Meta benchmark results")
        rows.extend(record["cases"])
    if len({r["scenario_id"] for r in rows}) != len(rows):
        parser.error("Duplicate scenario IDs would distort sample sizes")
    summary = {"mode": "LIVE_META_SUMMARY", "sample_size": len(rows), "metrics": metrics(rows),
               "scenarios": [{"id": r["scenario_id"], "outcome": r["outcome"],
                              "provenance": r["provenance"], "model_ids": ["muse-spark-1.3", "sam-3.1"],
                              "failed_safely": r.get("failed_safely"),
                              "failure_analysis": r.get("failure_analysis") or failure_analysis(r)}
                             for r in rows],
               "limitations": ["Synthetic scenes do not validate physical correction.",
                               "No region-level SKU ground truth; identification accuracy is unmeasured.",
                               "Uncertain outcomes are excluded from binary discrepancy precision and recall."]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Combined {len(rows)} real Meta evaluation results: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
