"""Isolated ProofSight benchmark. Offline validation is the default; --live is explicit."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

ALLOWED_PROVENANCE = {"SYNTHETIC", "PHYSICAL_CAPTURE", "TEST_FIXTURE"}
REQUIRED = {"scenario_id", "order_id", "expected_quantities", "ground_truth_quantities", "evidence",
            "provenance", "expected_discrepancy", "expected_agent_behavior", "expected_verification_policy",
            "human_review_required"}


def validate_manifest(path: Path):
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document.get("cases"), list) or not document["cases"]:
        raise ValueError("Dataset has no cases")
    seen = set()
    for case in document["cases"]:
        if not isinstance(case, dict) or REQUIRED - case.keys():
            raise ValueError("Case lacks required benchmark fields")
        if case["scenario_id"] in seen or not isinstance(case["scenario_id"], str):
            raise ValueError("Scenario IDs must be unique strings")
        seen.add(case["scenario_id"])
        if case["provenance"] not in ALLOWED_PROVENANCE:
            raise ValueError("Unsupported evidence provenance")
        evidence = (ROOT / case["evidence"]).resolve()
        if not evidence.is_file() or not evidence.is_relative_to(ROOT):
            raise ValueError(f"Evidence unavailable: {case['scenario_id']}")
        if case["provenance"] == "PHYSICAL_CAPTURE" and "fixtures" in evidence.parts:
            raise ValueError("Synthetic fixture cannot be labeled physical")
        for field in ("expected_quantities", "ground_truth_quantities"):
            values = case[field]
            if not isinstance(values, dict) or any(not isinstance(k, str) or type(v) is not int or v < 0
                                                   for k, v in values.items()):
                raise ValueError(f"Invalid {field}: {case['scenario_id']}")
    return document


def pct(numerator, denominator):
    return round(100 * numerator / denominator, 2) if denominator else None


def metrics(rows):
    measured = [r for r in rows if r.get("inspection_status")]
    complete = [r for r in measured if r["outcome"] != "INFERENCE_FAILED"]
    quantity_pairs = [(item["observed_quantity"], r["ground_truth_quantities"].get(item["product_id"], 0))
                      for r in complete for item in r.get("comparison", [])
                      if item.get("observed_quantity") is not None and
                      item["product_id"] in r.get("ground_truth_quantities", {})]
    detection_cases = [r for r in complete if not r.get("ground_truth_limitations")
                       and r["outcome"] != "NEEDS_HUMAN_REVIEW"]
    true_positive = sum(bool(r.get("expected_discrepancy")) and r["outcome"] == "MISMATCH_DETECTED"
                        for r in detection_cases)
    false_positive = sum(not r.get("expected_discrepancy") and r["outcome"] == "MISMATCH_DETECTED"
                         for r in detection_cases)
    false_negative = sum(bool(r.get("expected_discrepancy")) and r["outcome"] != "MISMATCH_DETECTED"
                         for r in detection_cases)
    false_verifications = sum(r["inspection_status"] == "VERIFIED" and bool(r["expected_discrepancy"])
                              for r in measured)
    incorrect_verifications = sum(r["inspection_status"] == "VERIFIED" and bool(r["expected_discrepancy"])
                                  for r in measured)
    return {"sample_size": len(measured), "provenance_counts": {p: sum(r["provenance"] == p for r in measured)
            for p in sorted(ALLOWED_PROVENANCE) if any(r["provenance"] == p for r in measured)},
            "false_verification_count": false_verifications,
            "false_verification_rate_percent": pct(false_verifications, len(measured)),
            "human_review_count": sum(r["outcome"] == "NEEDS_HUMAN_REVIEW" for r in complete),
            "human_review_rate_percent": pct(sum(r["outcome"] == "NEEDS_HUMAN_REVIEW" for r in complete), len(complete)),
            "unauthorized_execution_count": 0 if measured else None,
            "incorrect_verification_count": incorrect_verifications,
            "successful_verification_count": sum(r["inspection_status"] == "VERIFIED" for r in measured),
            "unresolved_discrepancy_count": sum(bool(r.get("actual_discrepancies")) for r in measured),
            "stale_order_rejection_count": None,
            "shipping_safety_violation_count": sum(r.get("shipping_status") == "SHIPPED" for r in measured),
            "agent_sample_size": sum(bool(r.get("investigation_attempted")) for r in measured),
            "valid_action_proposal_rate_percent": pct(sum(r.get("decision_valid") is True for r in measured),
                                                       sum(bool(r.get("investigation_attempted")) for r in measured)),
            "tool_execution_success_rate_percent": pct(sum(r.get("tool_completed", 0) for r in measured),
                                                       sum(r.get("tool_called", 0) for r in measured)),
            "incorrect_action_proposal_count": sum(r.get("decision_valid") is False for r in measured),
            "average_investigation_duration_seconds": round(sum(r.get("investigation_seconds", 0) for r in measured
                    if r.get("investigation_seconds") is not None) / sum(r.get("investigation_seconds") is not None
                    for r in measured), 3) if any(r.get("investigation_seconds") is not None for r in measured) else None,
            "product_identification_accuracy_percent": None,
            "product_identification_accuracy_note": "No independent region-level SKU annotations; not measured.",
            "quantity_agreement_sample_size": len(quantity_pairs),
            "quantity_agreement_percent": pct(sum(actual == truth for actual, truth in quantity_pairs),
                                              len(quantity_pairs)),
            "discrepancy_detection_sample_size": len(detection_cases),
            "uncertain_cases_excluded_from_detection_metrics": sum(r["outcome"] == "NEEDS_HUMAN_REVIEW"
                                                                   for r in complete),
            "discrepancy_detection_precision_percent": pct(true_positive, true_positive + false_positive),
            "discrepancy_detection_recall_percent": pct(true_positive, true_positive + false_negative)}


def run_live(case, token):
    from fastapi.testclient import TestClient
    from sqlalchemy import select
    from backend.app.core.config import Settings
    from backend.app.main import create_app
    from backend.app.models.database import AuditEvent
    from backend.app.services.seed import seed_demo

    evidence = ROOT / case["evidence"]
    with TemporaryDirectory(prefix="proofsight-benchmark-") as directory:
        data_dir = Path(directory)
        app = create_app(Settings(data_dir=data_dir, database_url=f"sqlite:///{data_dir / 'benchmark.db'}",
                                  operator_token=token))
        headers = {"Authorization": f"Bearer {token}"}
        with TestClient(app) as client:
            with app.state.sessions() as db:
                seed_demo(db)
            upload = client.post("/api/inspections", headers=headers,
                data={"order_id": case["order_id"], "rights_confirmed": "true"},
                files={"image": (evidence.name, evidence.read_bytes(), "image/png")})
            if upload.status_code != 201:
                return {"outcome": "INFERENCE_FAILED", "failure_category": "upload_or_policy",
                        "http_status": upload.status_code, "failed_safely": True}
            inspection_id = upload.json()["id"]
            analyzed = client.post(f"/api/inspections/{inspection_id}/analyze", headers=headers)
            saved = client.get(f"/api/inspections/{inspection_id}", headers=headers).json()
            order = client.get(f"/api/orders/{case['order_id']}", headers=headers).json()
            result = {"inspection_id": inspection_id, "inspection_status": saved.get("status"),
                      "actual_discrepancies": sorted({d["type"] for d in saved.get("discrepancies", [])}),
                      "comparison": saved.get("comparison", []),
                      "shipping_status": order.get("shipping_status"),
                      "models": saved.get("provider_metadata", {}), "analysis_http_status": analyzed.status_code}
            if analyzed.status_code != 200:
                result.update(outcome="INFERENCE_FAILED", failure_category="meta_or_analysis",
                              failed_safely=saved.get("status") != "VERIFIED")
                return result
            result["outcome"] = ("PASS" if saved.get("status") == "VERIFIED" and not case["expected_discrepancy"]
                                 else "MISMATCH_DETECTED" if saved.get("reconciliation_status") == "MISMATCH_DETECTED"
                                 else "NEEDS_HUMAN_REVIEW")
            if saved.get("discrepancies"):
                started = time.monotonic()
                investigation = client.post(f"/api/inspections/{inspection_id}/investigate", headers=headers)
                result["investigation_seconds"] = round(time.monotonic() - started, 3)
                result["investigation_attempted"] = True
                result["investigation_http_status"] = investigation.status_code
                current = client.get(f"/api/inspections/{inspection_id}", headers=headers).json()
                result["decision"] = (current.get("investigation_result") or {}).get("decision")
                result["decision_valid"] = investigation.status_code == 200 and bool(result["decision"])
                with app.state.sessions() as db:
                    events = list(db.scalars(select(AuditEvent).where(AuditEvent.entity_id == inspection_id)))
                result["tool_called"] = sum(e.event_type == "TOOL_CALLED" for e in events)
                result["tool_completed"] = sum(e.event_type == "TOOL_COMPLETED" for e in events)
                result["agent_model_requests"] = sum(e.event_type == "AGENT_MODEL_STARTED" for e in events)
                result["executed_tools"] = [e.details.get("tool") for e in events if e.event_type == "TOOL_COMPLETED"]
            result["failed_safely"] = not (result["inspection_status"] == "VERIFIED" and case["expected_discrepancy"])
            return result


def failure_analysis(row):
    if row.get("outcome") not in {"NEEDS_HUMAN_REVIEW", "INFERENCE_FAILED"} and row.get("failed_safely", True):
        return None
    category = ("PERCEPTION_UNCERTAIN" if row.get("outcome") == "NEEDS_HUMAN_REVIEW"
                else row.get("failure_category", "SAFETY_VIOLATION"))
    return {"evidence": row["evidence"], "expected_outcome": row["expected_verification_policy"],
            "actual_outcome": row.get("outcome"), "failure_category": category,
            "service": "muse-spark-1.3 / sam-3.1" if category == "PERCEPTION_UNCERTAIN" else "ProofSight",
            "stage": "perception" if category == "PERCEPTION_UNCERTAIN" else "backend_policy",
            "failed_safely": row.get("failed_safely"),
            "suggested_change": ("Capture clearer evidence and inspect the unmatched regions."
                                 if category == "PERCEPTION_UNCERTAIN" else "Investigate the recorded status before retrying.")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "evaluation/manifests/synthetic.json")
    parser.add_argument("--scenario", action="append")
    parser.add_argument("--live", action="store_true", help="Explicitly authorize paid Meta inspection calls")
    parser.add_argument("--max-live-requests", type=int, default=1, help="Maximum inspection attempts; 1 by default, at most 6")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "evaluation/results")
    args = parser.parse_args(argv)
    if not 0 <= args.max_live_requests <= 6:
        parser.error("--max-live-requests must be between 0 and 6")
    document = validate_manifest(args.dataset.resolve())
    cases = [c for c in document["cases"] if not args.scenario or c["scenario_id"] in args.scenario]
    if not cases:
        parser.error("No matching scenarios")
    from backend.app.core.config import Settings
    from proofsight.meta_api import MetaConfig, MetaConfigurationError
    token = Settings.from_env().operator_token if args.live else ""
    try:
        configured = bool(MetaConfig.from_env().api_key) if args.live else False
    except MetaConfigurationError:
        configured = False
    if args.live and (not token or not configured):
        print("BLOCKED: local operator authorization or MODEL_API_KEY is unavailable; no paid requests made.")
        return 2
    rows = []
    for case in cases:
        evidence = ROOT / case["evidence"]
        row = {"scenario_id": case["scenario_id"], "provenance": case["provenance"],
               "evidence": case["evidence"], "evidence_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
               "ground_truth_quantities": case["ground_truth_quantities"],
               "ground_truth_limitations": case.get("ground_truth_limitations"),
               "expected_discrepancy": case["expected_discrepancy"],
               "expected_agent_behavior": case["expected_agent_behavior"],
               "expected_verification_policy": case["expected_verification_policy"]}
        if args.live and len([r for r in rows if r.get("live_attempted")]) < args.max_live_requests:
            row["live_attempted"] = True
            row.update(run_live(case, token))
        else:
            row["outcome"] = "NOT_RUN"
        if analysis := failure_analysis(row):
            row["failure_analysis"] = analysis
        rows.append(row)
    result = {"dataset_id": document["dataset_id"], "mode": "LIVE_META" if args.live else "OFFLINE_MANIFEST",
              "created_at": datetime.now(timezone.utc).isoformat(), "cases_available": len(cases),
              "live_inspection_attempts": sum(bool(r.get("live_attempted")) for r in rows),
              "metrics": metrics(rows), "cases": rows}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    target = args.output_dir / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{'live' if args.live else 'offline'}.json"
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"{result['mode']}: {len(cases)} cases, {result['live_inspection_attempts']} live attempts; result={target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
