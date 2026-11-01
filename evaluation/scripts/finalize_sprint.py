"""Combine existing live records without making another provider request."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import median


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("evaluation/results"))
    args = parser.parse_args()
    cases = []
    for path in args.results:
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("mode") != "LIVE_META" or report.get("live_inspection_attempts") != 1:
            parser.error(f"Not a single-case live record: {path}")
        case = next(row for row in report["cases"] if row.get("live_attempted"))
        meta = case.get("models") or {}
        cases.append({"scenario_id": case["scenario_id"], "provenance": case["provenance"],
                      "outcome": case.get("outcome"), "inspection_status": case.get("inspection_status"),
                      "inspection_latency_ms": meta.get("total_latency_ms"),
                      "muse_latency_ms": meta.get("muse_latency_ms"),
                      "sam_latency_ms": meta.get("sam_latency_ms"),
                      "muse_requests": 1 if meta.get("muse_model") else 0,
                      "sam_requests": meta.get("sam_requests", 0),
                      "agent_requests": case.get("agent_model_requests", 0),
                      "tool_called": case.get("tool_called", 0),
                      "tool_completed": case.get("tool_completed", 0),
                      "shipping_status": case.get("shipping_status"),
                      "source_result": str(path)})
    latencies = [row["inspection_latency_ms"] for row in cases if row["inspection_latency_ms"] is not None]
    report = {"live_cases": len(cases), "synthetic_cases": sum(row["provenance"] == "SYNTHETIC" for row in cases),
              "physical_cases": sum(row["provenance"] == "PHYSICAL_CAPTURE" for row in cases),
              "paid_model_requests": sum(row["muse_requests"] + row["sam_requests"] + row["agent_requests"] for row in cases),
              "inspection_latency_median_ms": median(latencies) if latencies else None,
              "latency_sample_size": len(latencies), "api_cost": "UNKNOWN",
              "false_verifications": sum(row["inspection_status"] == "VERIFIED" and row["outcome"] != "PASS" for row in cases),
              "shipping_safety_violations": sum(row["shipping_status"] == "SHIPPED" and row["inspection_status"] != "VERIFIED" for row in cases),
              "uncertain_outcomes": sum(row["outcome"] == "NEEDS_HUMAN_REVIEW" for row in cases),
              "cases": cases}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "final-benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    with (args.output_dir / "final-benchmark.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=cases[0].keys())
        writer.writeheader()
        writer.writerows(cases)
    print(f"Combined {len(cases)} live cases; {report['paid_model_requests']} model requests; no new inference")


if __name__ == "__main__":
    main()
