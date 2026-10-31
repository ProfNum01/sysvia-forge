"""One isolated synthetic extra-product inspection and real Meta investigation."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.models.database import AuditEvent
from backend.app.services.seed import seed_demo


def main():
    root = Path(__file__).resolve().parents[1]
    token = Settings.from_env().operator_token
    if not token:
        print("blocked=operator_auth_unavailable")
        return 2
    with TemporaryDirectory() as directory:
        data_dir = Path(directory)
        app = create_app(Settings(data_dir=data_dir, database_url=f"sqlite:///{data_dir / 'live.db'}",
                                  operator_token=token))
        headers = {"Authorization": f"Bearer {token}"}
        with TestClient(app) as client:
            with app.state.sessions() as db:
                seed_demo(db)
            fixture = root / "data/fixtures/task002-extra.png"
            upload = client.post("/api/inspections", headers=headers,
                data={"order_id": "order-1001", "rights_confirmed": "true"},
                files={"image": (fixture.name, fixture.read_bytes(), "image/png")})
            if upload.status_code != 201:
                print(f"upload_http={upload.status_code}")
                return 1
            inspection_id = upload.json()["id"]
            analyzed = client.post(f"/api/inspections/{inspection_id}/analyze", headers=headers)
            body = analyzed.json()
            print(f"synthetic_fixture=True analyze_http={analyzed.status_code} "
                  f"reconciliation={body.get('reconciliation_status')} "
                  f"discrepancies={sorted({row['type'] for row in body.get('discrepancies', [])})}", flush=True)
            if analyzed.status_code != 200 or not body.get("discrepancies"):
                return 1
            investigated = client.post(f"/api/inspections/{inspection_id}/investigate", headers=headers)
            decision = investigated.json()
            with app.state.sessions() as db:
                calls = db.scalar(select(func.count()).select_from(AuditEvent).where(
                    AuditEvent.entity_id == inspection_id, AuditEvent.event_type == "AGENT_MODEL_STARTED"))
                tools = db.scalar(select(func.count()).select_from(AuditEvent).where(
                    AuditEvent.entity_id == inspection_id, AuditEvent.event_type == "TOOL_COMPLETED"))
            print(f"investigate_http={investigated.status_code} "
                  f"decision={(decision.get('investigation_result') or {}).get('decision')} "
                  f"actions={sorted({row['type'] for row in decision.get('actions', [])})} "
                  f"live_agent_calls={calls} completed_tools={tools} shipping="
                  f"{client.get('/api/orders/order-1001', headers=headers).json().get('shipping_status')}", flush=True)
            return 0 if investigated.status_code == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
