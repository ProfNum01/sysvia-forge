"""Isolated synthetic fixture workflow with real Meta inference; no business data."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.services.seed import seed_demo


def main():
    root = Path(__file__).resolve().parents[1]
    token = Settings.from_env().operator_token
    if not token:
        print("blocked=operator_auth_unavailable")
        return 2
    headers = {"Authorization": f"Bearer {token}"}
    with TemporaryDirectory() as directory:
        data_dir = Path(directory)
        settings = Settings(data_dir=data_dir, database_url=f"sqlite:///{data_dir / 'flow.db'}",
                            operator_token=token)
        app = create_app(settings)
        with TestClient(app) as client:
            with app.state.sessions() as db:
                seed_demo(db)
            before = root / "data/fixtures/task002-missing.png"
            after = root / "data/fixtures/task002-correct.png"
            print("synthetic_fixture=True physical_pick=False", flush=True)
            original = client.post("/api/inspections", headers=headers,
                data={"order_id": "order-1001", "rights_confirmed": "true"},
                files={"image": ("before.png", before.read_bytes(), "image/png")})
            if original.status_code != 201:
                print(f"upload_before_http={original.status_code}")
                return 1
            original_id = original.json()["id"]
            analyzed = client.post(f"/api/inspections/{original_id}/analyze", headers=headers)
            print(f"analyze_before_http={analyzed.status_code} status={analyzed.json().get('status')}", flush=True)
            if analyzed.status_code != 200 or analyzed.json().get("status") != "NEEDS_REVIEW":
                return 1
            investigation = client.post(f"/api/inspections/{original_id}/investigate", headers=headers)
            body = investigation.json()
            print(f"investigate_http={investigation.status_code} status={body.get('investigation_status')} "
                  f"decision={(body.get('investigation_result') or {}).get('decision')} "
                  f"actions={len(body.get('actions', []))}", flush=True)
            if investigation.status_code != 200:
                return 1
            for action in body.get("actions", []):
                action_id = action["id"]
                if action["status"] not in ("PROPOSED", "PENDING_APPROVAL"):
                    continue
                approved = client.post(f"/api/actions/{action_id}/approve", headers=headers,
                    json={"idempotency_key": f"fixture-approve-{action_id}"})
                if approved.status_code != 200:
                    print(f"approve_http={approved.status_code}")
                    return 1
                executed = client.post(f"/api/actions/{action_id}/execute", headers=headers,
                    json={"idempotency_key": f"fixture-execute-{action_id}"})
                print(f"action_type={action['type']} execute_http={executed.status_code}", flush=True)
                if executed.status_code != 200:
                    return 1
                if action["type"] == "CREATE_PICKING_TASK":
                    print("fixture_picking_completion_simulated=True", flush=True)
                    task_id = executed.json()["execution_details"]["task_id"]
                    completion = client.post(f"/api/picking-tasks/{task_id}/complete", headers=headers,
                        json={"idempotency_key": f"fixture-complete-{task_id}"})
                    if completion.status_code != 200:
                        print(f"fixture_pick_http={completion.status_code}")
                        return 1
            replacement = client.post(f"/api/inspections/{original_id}/reinspect", headers=headers,
                data={"rights_confirmed": "true"},
                files={"image": ("after.png", after.read_bytes(), "image/png")})
            print(f"upload_after_http={replacement.status_code}", flush=True)
            if replacement.status_code != 201:
                return 1
            after_id = replacement.json()["id"]
            verified = client.post(f"/api/inspections/{after_id}/analyze", headers=headers)
            order = client.get("/api/orders/order-1001", headers=headers).json()
            print(f"analyze_after_http={verified.status_code} status={verified.json().get('status')} "
                  f"shipping={order.get('shipping_status')} revision_current="
                  f"{verified.json().get('order_version') == order.get('version')}", flush=True)
            return 0 if verified.status_code == 200 and verified.json().get("status") == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
