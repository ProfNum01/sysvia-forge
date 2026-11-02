import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.models.database import AuditEvent, Order
from backend.app.services.catalog import reference_path
from sqlalchemy import select


def image_bytes(color):
    output = io.BytesIO()
    Image.new("RGB", (80, 80), color).save(output, "PNG")
    return output.getvalue()


def test_create_isolated_test_order_with_references_and_idempotency():
    with tempfile.TemporaryDirectory() as folder:
        app = create_app(Settings(database_url=f"sqlite:///{Path(folder) / 'test.db'}",
                                  data_dir=Path(folder), operator_token="test-operator"))
        with TestClient(app) as client:
            payload = {"reference": "MY-TEST-001", "customer": "Local demo",
                       "items": [{"sku": "MY-BLUE", "name": "Blue cube", "color": "blue", "quantity": 2,
                                  "visible_label": False},
                                 {"sku": "MY-GREEN", "name": "Green cube", "color": "green", "quantity": 1,
                                  "visible_label": False}]}
            files = [("references", ("blue.png", image_bytes("blue"), "image/png")),
                     ("references", ("green.png", image_bytes("green"), "image/png"))]
            headers = {"Authorization": "Bearer test-operator", "Idempotency-Key": "my-test-order-001"}
            data = {"manifest": json.dumps(payload), "rights_confirmed": "true"}
            response = client.post("/api/orders/test", data=data, files=files, headers=headers)
            assert response.status_code == 201, response.text
            created = response.json()
            assert created["reference"] == "MY-TEST-001"
            assert created["data_source"] == "synthetic_user"
            assert [item["quantity"] for item in created["items"]] == [2, 1]
            assert all(item["product"]["reference_image_url"] for item in created["items"])
            assert all(client.get(item["product"]["reference_image_url"], headers=headers).status_code == 200
                       for item in created["items"])
            with app.state.sessions() as db:
                order = db.get(Order, created["id"])
                assert all(reference_path(Path(folder), item.product.id, item.product.sku,
                                          item.product.registered_reference_path) for item in order.items)
                assert db.scalar(select(AuditEvent).where(AuditEvent.entity_id == created["id"],
                                                         AuditEvent.event_type == "TEST_ORDER_CREATED"))
            replay = client.post("/api/orders/test", data=data, files=files, headers=headers)
            assert replay.status_code == 200
            assert replay.json()["id"] == created["id"]
            changed = {**payload, "items": [{**payload["items"][0], "quantity": 3}, payload["items"][1]]}
            conflict = client.post("/api/orders/test", data={**data, "manifest": json.dumps(changed)},
                                   files=files, headers=headers)
            assert conflict.status_code == 409
            inspection = client.post("/api/inspections", data={"order_id": created["id"],
                "rights_confirmed": "true"}, files={"image": ("scene.png", image_bytes("white"), "image/png")},
                headers=headers)
            assert inspection.status_code == 201, inspection.text
            model_result = {"muse": {"ok": True, "observations": [], "model": "test-muse", "http_status": 200},
                            "sam": {"ok": True, "boxes": [], "masks": [], "model": "test-sam",
                                    "http_status": 200, "requests": 1}, "regions": [], "observations": []}
            with patch("backend.app.api.routes.run_visual_models", return_value=model_result) as provider:
                analyzed = client.post(f"/api/inspections/{inspection.json()['id']}/analyze", headers=headers)
            assert analyzed.status_code == 200, analyzed.text
            model_catalog = provider.call_args.args[1]
            assert {product["sku"] for product in model_catalog} == {"MY-BLUE", "MY-GREEN"}
            assert all(product["reference_image_path"] for product in model_catalog)
        app.state.engine.dispose()


def test_test_order_rejects_untrusted_or_invalid_inputs():
    with tempfile.TemporaryDirectory() as folder:
        app = create_app(Settings(database_url=f"sqlite:///{Path(folder) / 'test.db'}",
                                  data_dir=Path(folder), operator_token="test-operator"))
        with TestClient(app) as client:
            payload = {"reference": "MY-TEST-002", "customer": "Local demo",
                       "items": [{"sku": "MY-RED", "name": "Red cube", "color": "red", "quantity": 1}]}
            files = [("references", ("red.png", image_bytes("red"), "image/png"))]
            data = {"manifest": json.dumps(payload), "rights_confirmed": "true"}
            assert client.post("/api/orders/test", data=data, files=files).status_code == 403
            headers = {"Authorization": "Bearer test-operator", "Idempotency-Key": "my-test-order-002"}
            assert client.post("/api/orders/test", data={**data, "rights_confirmed": "false"},
                               files=files, headers=headers).status_code == 422
            assert client.post("/api/orders/test", data=data, files=[], headers=headers).status_code == 422
            assert client.post("/api/orders/test", data=data,
                               files=[("references", ("bad.png", b"not an image", "image/png"))],
                               headers=headers).status_code == 422
            with app.state.sessions() as db:
                assert db.scalar(select(Order).where(Order.reference == "MY-TEST-002")) is None
        app.state.engine.dispose()
