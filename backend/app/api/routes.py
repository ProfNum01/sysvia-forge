from __future__ import annotations

import hmac
import re
import time
from collections import Counter
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import object_session
from pydantic import ValidationError

from backend.app.models.database import (Approval, AuditEvent, CorrectiveAction, Discrepancy, Inspection,
    InspectionObservation, Inventory, Order, Product, audit)
from backend.app.schemas.responses import (ActionOut, AuditOut, DashboardOut, HealthOut, IdempotentRequest,
    EvidenceRegion, InspectionOut, MetaStatusOut, ObservationInput, OrderOut, ProductOut)
from backend.app.services.catalog import reference_path
from backend.app.services.investigation import investigate_with_read_tools
from backend.app.services.inventory import available_quantity
from backend.app.services.media import prepare_image
from backend.app.services.provider import run_visual_models
from backend.app.services.reconciliation import reconcile
from proofsight.meta_api import MetaConfig, MetaConfigurationError, classify_api_error

router = APIRouter(prefix="/api")


def database(request: Request):
    with request.app.state.sessions() as db:
        yield db


def supervisor(request: Request, authorization: Annotated[str | None, Header()] = None):
    expected = request.app.state.settings.operator_token
    if not expected:
        raise HTTPException(503, "Local supervisor authorization is not configured. Set OPERATOR_TOKEN in .env.")
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(token.encode(), expected.encode()):
        raise HTTPException(403, "A trusted supervisor token is required.")
    return "local-supervisor"


def required(db, model, identifier):
    row = db.get(model, identifier)
    if row is None:
        raise HTTPException(404, "Record was not found.")
    return row


def inspection_out(inspection):
    output = InspectionOut.model_validate(inspection)
    output.image_url = f"/api/inspections/{inspection.id}/image"
    if (Path(inspection.image_path).parent / f"{inspection.id}-annotated.png").is_file():
        output.annotation_url = f"/api/inspections/{inspection.id}/annotation"
    db = object_session(inspection)
    if db is not None:
        output.execution_events = list(db.scalars(select(AuditEvent).where(
            AuditEvent.entity_id == inspection.id).order_by(AuditEvent.created_at, AuditEvent.id)))
    output.unidentified_objects = [o for o in output.observations if o.identification_status == "UNIDENTIFIED"]
    return output


def require_current(db, inspection):
    order = required(db, Order, inspection.order_id)
    if order.latest_inspection_id != inspection.id:
        raise HTTPException(409, "A newer inspection exists. This evidence and its actions are superseded.")
    return order


@router.get("/health", response_model=HealthOut)
def health(db=Depends(database)):
    db.execute(select(1)).scalar_one()
    return {"status": "ok", "database": "ready"}


@router.get("/orders", response_model=list[OrderOut])
def orders(db=Depends(database)):
    return list(db.scalars(select(Order).order_by(Order.reference)))


@router.get("/products", response_model=list[ProductOut])
def product_catalog(db=Depends(database)):
    return list(db.scalars(select(Product).order_by(Product.sku)))


@router.get("/products/{product_id}/reference")
def product_reference(request: Request, product_id: str, db=Depends(database)):
    product = required(db, Product, product_id)
    path = reference_path(request.app.state.settings.data_dir, product.id, product.sku)
    if path is None or not path.is_file():
        raise HTTPException(404, "A rights-cleared product reference is not available.")
    return FileResponse(path, media_type="image/png", headers={"X-Content-Type-Options": "nosniff"})


@router.get("/orders/{order_id}", response_model=OrderOut)
def order_detail(order_id: str, db=Depends(database)):
    return required(db, Order, order_id)


@router.get("/inspections", response_model=list[InspectionOut])
def inspections(db=Depends(database)):
    return [inspection_out(i) for i in db.scalars(select(Inspection).order_by(Inspection.created_at.desc()).limit(100))]


@router.get("/dashboard/summary", response_model=DashboardOut)
def dashboard(db=Depends(database)):
    states = Counter(db.scalars(select(Order.status)))
    return {
        "total_orders": sum(states.values()), "pending_inspections": sum(v for k, v in states.items() if k != "VERIFIED"),
        "verified_orders": states["VERIFIED"],
        "active_discrepancies": db.scalar(select(func.count()).select_from(Discrepancy)
            .join(Order, Order.latest_inspection_id == Discrepancy.inspection_id).where(Discrepancy.status == "OPEN")),
        "order_status_distribution": [{"status": status, "count": count} for status, count in states.items()],
        "recent_inspections": [inspection_out(i) for i in db.scalars(select(Inspection).order_by(Inspection.created_at.desc()).limit(6))],
        "agent_activity": list(db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(10))),
    }


@router.get("/integrations/meta/status", response_model=MetaStatusOut)
def meta_status(request: Request):
    try:
        status = MetaConfig.from_env().public_status()
    except MetaConfigurationError:
        status = {"configured": False, "base_url": "https://api.meta.ai/v1",
                  "muse_model": "muse-spark-1.3", "sam_model": "sam-3.1"}
    return {**status, "operator_auth_configured": bool(request.app.state.settings.operator_token),
            "configuration_location": ".env (repository root), or PROOFSIGHT_ENV_FILE",
            "last_live_check": (request.app.state.live_check or {}).get("checked_at"),
            "last_live_result": request.app.state.live_check,
            "note": "Configured does not mean connected. Status checks do not call paid model APIs."}


def create_inspection(request, db, order_id, image, rights_confirmed, parent=None, creation_key=None):
    if not rights_confirmed:
        raise HTTPException(422, "Confirm that the image is synthetic or you have rights to use it.")
    if creation_key is not None and not re.fullmatch(r"[a-zA-Z0-9_-]{8,100}", creation_key):
        raise HTTPException(422, "Idempotency-Key must be 8–100 letters, digits, underscores, or hyphens.")
    photo_id, digest, destination, content, width, height = prepare_image(image, request.app.state.settings)
    if creation_key:
        existing = db.scalar(select(Inspection).where(Inspection.creation_key == creation_key))
        if existing:
            if (existing.order_id != order_id or existing.image_sha256 != digest
                    or existing.previous_inspection_id != (parent.id if parent else None)):
                raise HTTPException(409, "This idempotency key belongs to different inspection evidence.")
            return inspection_out(existing)
    order = required(db, Order, order_id)
    if order.latest_inspection_id:
        latest = required(db, Inspection, order.latest_inspection_id)
        if latest.status == "ANALYZING":
            raise HTTPException(409, "The current inspection is being analyzed.")
        if parent is None:
            raise HTTPException(409, "Use reinspection to attach new evidence to the existing inspection chain.")
        if latest.id != parent.id:
            raise HTTPException(409, "Reinspection must use the latest inspection.")
    if parent is not None and parent.status in {"UPLOADED", "ANALYZING"}:
        raise HTTPException(409, "Analyze the current image before requesting reinspection.")
    if parent:
        prior = parent
        while prior:
            if prior.image_sha256 == digest:
                raise HTTPException(409, "New visual evidence is required. This image matches an earlier photo.")
            prior = db.get(Inspection, prior.previous_inspection_id) if prior.previous_inspection_id else None
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    inspection = Inspection(order_id=order.id, photo_id=photo_id, image_path=str(destination),
                            image_sha256=digest, image_width=width, image_height=height, creation_key=creation_key,
                            processing_stage="IMAGE_VALIDATED", previous_inspection_id=parent.id if parent else None)
    try:
        db.add(inspection)
        db.flush()
        order.latest_inspection_id = inspection.id
        if order.status != "HELD":
            order.status = "PENDING_INSPECTION"
        audit(db, "REINSPECTION_UPLOADED" if parent else "IMAGE_UPLOADED", inspection.id,
              {"photo_id": photo_id, "order_id": order.id, "previous_photo_id": parent.photo_id if parent else None}, actor="operator-upload")
        audit(db, "IMAGE_VALIDATED", inspection.id, {"width": width, "height": height, "format": "PNG"})
        db.commit()
    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise
    return inspection_out(inspection)


@router.post("/inspections", response_model=InspectionOut, status_code=201)
def upload_inspection(request: Request, order_id: Annotated[str, Form()],
                      image: Annotated[UploadFile, File()], rights_confirmed: Annotated[bool, Form()] = False,
                      idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
                      actor=Depends(supervisor), db=Depends(database)):
    with request.app.state.mutations:
        return create_inspection(request, db, order_id, image, rights_confirmed, creation_key=idempotency_key)


@router.post("/inspections/{inspection_id}/reinspect", response_model=InspectionOut, status_code=201)
def reinspect(request: Request, inspection_id: str, image: Annotated[UploadFile, File()],
              rights_confirmed: Annotated[bool, Form()] = False,
              idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
              actor=Depends(supervisor), db=Depends(database)):
    with request.app.state.mutations:
        parent = required(db, Inspection, inspection_id)
        return create_inspection(request, db, parent.order_id, image, rights_confirmed, parent, creation_key=idempotency_key)


@router.get("/inspections/{inspection_id}", response_model=InspectionOut)
@router.get("/inspections/{inspection_id}/results", response_model=InspectionOut)
def inspection_detail(inspection_id: str, db=Depends(database)):
    return inspection_out(required(db, Inspection, inspection_id))


@router.get("/inspections/{inspection_id}/image")
def image_file(inspection_id: str, db=Depends(database)):
    return FileResponse(required(db, Inspection, inspection_id).image_path, media_type="image/png",
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/inspections/{inspection_id}/annotation")
def annotation_file(inspection_id: str, db=Depends(database)):
    inspection = required(db, Inspection, inspection_id)
    path = Path(inspection.image_path).parent / f"{inspection.id}-annotated.png"
    if not path.is_file():
        raise HTTPException(404, "No real segmentation annotation is available.")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})


def fail_provider(db, inspection, category, http_status=502, provider_http_status=None):
    db.expire_all()
    inspection = required(db, Inspection, inspection.id)
    require_current(db, inspection)
    if inspection.status != "ANALYZING":
        raise HTTPException(409, "This analysis was interrupted. Its failure did not change newer evidence.")
    inspection.status = "PROVIDER_ERROR"
    inspection.processing_stage = "PROVIDER_ERROR"
    inspection.provider_error = f"Meta provider error: {category}. No substitute model results were used."
    inspection.provider_error_details = {"category": category, "http_status": provider_http_status,
                                        "retryable": category in {"rate_limit", "timeout", "connection", "service_error"}}
    audit(db, "PROVIDER_ERROR", inspection.id, {"category": category, "http_status": provider_http_status})
    db.commit()
    raise HTTPException(http_status, inspection.provider_error)


@router.post("/inspections/{inspection_id}/analyze", response_model=InspectionOut)
def analyze(request: Request, inspection_id: str, actor=Depends(supervisor), db=Depends(database)):
    start = time.perf_counter()
    with request.app.state.mutations:
        inspection = required(db, Inspection, inspection_id)
        order = require_current(db, inspection)
        if order.preparation_status == "PREPARING":
            raise HTTPException(409, "The order preparation must be ready before inspection.")
        changed = db.execute(update(Inspection).where(Inspection.id == inspection_id,
            Inspection.status.in_(["UPLOADED", "PROVIDER_ERROR"])).values(status="ANALYZING"))
        if not changed.rowcount:
            raise HTTPException(409, "This image has already been analyzed or is being analyzed. Submit a new photo.")
        inspection.provider_error = None
        inspection.provider_error_details = None
        inspection.processing_stage = "ANALYSIS_STARTED"
        audit(db, "ANALYSIS_STARTED", inspection.id, {"photo_id": inspection.photo_id}, actor=actor)
        db.commit()
        products = [{"id": p.id, "sku": p.sku, "name": p.name, "color": p.color, "description": p.description,
                     "reference_image_path": str(reference_path(request.app.state.settings.data_dir, p.id, p.sku))
                         if reference_path(request.app.state.settings.data_dir, p.id, p.sku) else None}
                    for p in db.scalars(select(Product).order_by(Product.id).limit(4))]
    allowed_events = {"MUSE_ANALYSIS_STARTED", "MUSE_ANALYSIS_COMPLETED",
                      "SAM_SEGMENTATION_STARTED", "SAM_SEGMENTATION_COMPLETED"}

    def stage_event(stage, details):
        if stage not in allowed_events:
            raise ValueError("Unsupported processing event")
        safe = {key: details[key] for key in ("model", "product_id", "http_status", "latency_ms", "usage", "ok") if key in details}
        with request.app.state.mutations, request.app.state.sessions() as progress:
            current = progress.get(Inspection, inspection_id)
            current_order = progress.get(Order, current.order_id)
            if current.status == "ANALYZING" and current_order.latest_inspection_id == current.id:
                current.processing_stage = stage
                metadata = dict(current.provider_metadata or {})
                if stage == "MUSE_ANALYSIS_COMPLETED":
                    metadata.update(muse_model=details.get("model"), muse_latency_ms=details.get("latency_ms"),
                                    muse_usage=details.get("usage"), muse_http_status=details.get("http_status"))
                if stage == "SAM_SEGMENTATION_COMPLETED":
                    metadata.update(sam_model=details.get("model"), sam_http_status=details.get("http_status"))
                current.provider_metadata = metadata
                audit(progress, stage, current.id, safe, actor="meta-provider")
                progress.commit()
    try:
        result = run_visual_models(inspection.image_path, products,
                                   Path(inspection.image_path).parent / f"{inspection.id}-annotated.png", on_event=stage_event)
    except MetaConfigurationError:
        return fail_provider(db, inspection, "MODEL_API_KEY missing; configure the root .env file", 503)
    except Exception as exc:
        error = classify_api_error(exc)
        return fail_provider(db, inspection, error["category"], provider_http_status=error.get("http_status"))
    if not result.get("muse", {}).get("ok"):
        error = result.get("muse", {}).get("error") or {}
        return fail_provider(db, inspection, error.get("category", "visual_analysis_failed"),
                             429 if error.get("category") == "rate_limit" else 502, error.get("http_status"))
    sam = result.get("sam")
    if not sam or not sam.get("ok"):
        error = (sam or {}).get("error") or {}
        return fail_provider(db, inspection, error.get("category", "segmentation_failed"),
                             429 if error.get("category") == "rate_limit" else 502, error.get("http_status"))
    with request.app.state.mutations:
        db.expire_all()
        inspection = required(db, Inspection, inspection_id)
        require_current(db, inspection)
        if inspection.status != "ANALYZING":
            raise HTTPException(409, "This analysis was interrupted or superseded. Its output was not applied.")
        try:
            regions = [EvidenceRegion.model_validate(r).model_dump() for r in result.get("regions", [])]
            observations = [ObservationInput.model_validate(o).model_dump() for o in result.get("observations", [])]
            known_ids = {p["id"] for p in products}
            if len(regions) > 2000 or len(observations) > 1000:
                raise ValueError("Oversized perception result")
            for region in regions:
                boxes = [region["box"]] + ([region["mask"]["bounds"]] if region["mask"] else [])
                if (any(b["right"] > inspection.image_width or b["bottom"] > inspection.image_height for b in boxes)
                        or any(region[key] is not None and region[key] not in known_ids
                               for key in ("product_id", "candidate_product_id"))):
                    raise ValueError("Invalid source geometry")
        except (ValidationError, ValueError, TypeError):
            return fail_provider(db, inspection, "invalid_structured_evidence")
        return finish_analysis(db, inspection, result, sam, products, observations, regions,
                               round((time.perf_counter()-start)*1000))


def finish_analysis(db, inspection, result, sam, products, observations, regions, latency_ms):
    finish_start = time.perf_counter()
    order = require_current(db, inspection)
    expected = [{"product_id": line.product_id, "sku": line.product.sku, "name": line.product.name,
                 "quantity": line.quantity} for line in order.items]
    reconciliation = reconcile(expected, observations, bool(regions), catalog=products, regions=regions)
    accepted_ids = {rid for row in reconciliation["observations"] if row["identification_status"] == "MATCHED"
                    for rid in row["evidence_region_ids"]}
    for region in regions:
        if region["id"] not in accepted_ids:
            region["product_id"] = None
    inspection.regions = regions
    inspection.comparison = reconciliation["comparison"]
    inspection.reconciliation_status = reconciliation["reconciliation_status"]
    audit(db, "PRODUCT_MATCHING_COMPLETED", inspection.id, {"matched": sum(
        o["identification_status"] == "MATCHED" for o in reconciliation["observations"]),
        "uncertain": sum(o["identification_status"] != "MATCHED" for o in reconciliation["observations"])})
    for observation in reconciliation["observations"]:
        db.add(InspectionObservation(inspection_id=inspection.id, **observation))
    for discrepancy in reconciliation["discrepancies"]:
        db.add(Discrepancy(inspection_id=inspection.id, **discrepancy))
    inspection.segmentations = [{"boxes": sam.get("boxes", []), "masks": sam.get("masks", []),
                                "note": "SAM geometry does not independently establish product SKU."}]
    inspection.provider_metadata = {"muse_model": result["muse"].get("model"),
        "muse_usage": result["muse"].get("usage"), "muse_latency_ms": result["muse"].get("latency_ms"),
        "sam_latency_ms": sam.get("latency_ms"), "sam_model": "sam-3.1", "total_latency_ms": latency_ms,
        "muse_http_status": result["muse"].get("http_status"), "sam_http_status": sam.get("http_status"),
        "sam_requests": sam.get("requests"), "analysis_version": 2}
    if reconciliation["verified"]:
        inspection.status = "VERIFIED"
        order.status = "VERIFIED"
        order.preparation_status = "VERIFIED_BY_NEW_EVIDENCE"
        prior = db.get(Inspection, inspection.previous_inspection_id) if inspection.previous_inspection_id else None
        while prior:
            prior.resolved_by_inspection_id = inspection.id
            for discrepancy in prior.discrepancies:
                discrepancy.status = "RESOLVED"
            prior = db.get(Inspection, prior.previous_inspection_id) if prior.previous_inspection_id else None
        audit(db, "EVIDENCE_RECONCILED", inspection.id, {"photo_id": inspection.photo_id,
              "previous_inspection_id": inspection.previous_inspection_id})
    else:
        inspection.status = "NEEDS_REVIEW"
        if order.status != "HELD":
            order.status = "NEEDS_REVIEW"
        db.add(CorrectiveAction(inspection_id=inspection.id, type="HOLD_ORDER",
                               proposal="Hold this order for human review. Visual evidence has unresolved discrepancies."))
        audit(db, "DISCREPANCIES_DETECTED", inspection.id, {"count": len(reconciliation["discrepancies"])})
    latency_ms += round((time.perf_counter()-finish_start)*1000)
    inspection.provider_metadata = {**inspection.provider_metadata, "total_latency_ms": latency_ms}
    audit(db, "ANALYSIS_COMPLETED", inspection.id, {"status": inspection.status, "models": ["muse-spark-1.3", "sam-3.1"]})
    inspection.processing_stage = "RECONCILIATION_COMPLETED"
    audit(db, "RECONCILIATION_COMPLETED", inspection.id,
          {"status": inspection.reconciliation_status, "latency_ms": latency_ms})
    db.commit()
    db.refresh(inspection)
    return inspection_out(inspection)


@router.post("/inspections/{inspection_id}/investigate", response_model=InspectionOut)
def investigate(request: Request, inspection_id: str, actor=Depends(supervisor), db=Depends(database)):
    with request.app.state.mutations:
        inspection = required(db, Inspection, inspection_id)
        order = require_current(db, inspection)
        if inspection.status not in {"NEEDS_REVIEW", "HELD"}:
            raise HTTPException(409, "Investigation requires analyzed, unresolved evidence.")
        if inspection.investigation:
            return inspection_out(inspection)
        try:
            summary = investigate_with_read_tools(db, inspection, order)
        except MetaConfigurationError:
            raise HTTPException(503, "MODEL_API_KEY is missing. Configure the root .env file.") from None
        except Exception as exc:
            audit(db, "INVESTIGATION_FAILED", inspection.id, {"category": classify_api_error(exc)["category"]})
            db.commit()
            raise HTTPException(502, "Meta inventory investigation failed. No corrective action was executed.") from None
        inspection.investigation = summary.summary
        # Policy uses database quantities, never the model's recommendation as an executable instruction.
        for discrepancy in inspection.discrepancies:
            if discrepancy.type != "SHORTFALL" or discrepancy.observed_quantity is None:
                continue
            amount = discrepancy.required_quantity - discrepancy.observed_quantity
            inventory = db.scalar(select(Inventory).where(Inventory.product_id == discrepancy.product_id))
            if amount > 0 and inventory and available_quantity(db, discrepancy.product_id) >= amount:
                db.add(CorrectiveAction(inspection_id=inspection.id, product_id=discrepancy.product_id,
                    quantity=amount, type="CREATE_PICKING_TASK",
                    proposal=f"Create a picking task for {amount} unit(s) from {inventory.location}. New visual evidence remains required."))
        audit(db, "INVESTIGATION_COMPLETED", inspection.id, {"recommendation": summary.recommendation,
              "write_operations": 0, "tools": ["get_order", "get_inventory"]}, actor="meta-read-tool")
        db.commit()
        db.refresh(inspection)
        return inspection_out(inspection)


def validate_action(db, action):
    inspection = required(db, Inspection, action.inspection_id)
    order = require_current(db, inspection)
    if inspection.status not in {"NEEDS_REVIEW", "HELD"}:
        raise HTTPException(409, "This evidence no longer supports a corrective action.")
    if action.type == "CREATE_PICKING_TASK":
        discrepancy = next((d for d in inspection.discrepancies if d.type == "SHORTFALL"
                            and d.product_id == action.product_id and d.status == "OPEN"), None)
        inventory = db.scalar(select(Inventory).where(Inventory.product_id == action.product_id))
        if (not inspection.investigation or not discrepancy or discrepancy.observed_quantity is None
                or not inventory or not action.quantity or available_quantity(db, action.product_id) < action.quantity
                or action.quantity != discrepancy.required_quantity - discrepancy.observed_quantity):
            raise HTTPException(409, "Current evidence and inventory do not authorize this picking task.")
    elif action.type != "HOLD_ORDER":
        raise HTTPException(422, "Action type is not permitted by deterministic policy.")
    return inspection, order


@router.post("/actions/{action_id}/approve", response_model=ActionOut)
def approve(request: Request, action_id: str, body: IdempotentRequest, actor=Depends(supervisor), db=Depends(database)):
    with request.app.state.mutations:
        action = required(db, CorrectiveAction, action_id)
        validate_action(db, action)
        existing = db.scalar(select(Approval).where(Approval.action_id == action.id))
        if existing:
            if existing.idempotency_key != body.idempotency_key:
                raise HTTPException(409, "Action already has an approval under a different idempotency key.")
            return action
        if action.status != "PROPOSED":
            raise HTTPException(409, "Only a proposed action can be approved.")
        action.status = "APPROVED"
        db.add(Approval(action_id=action.id, operator=actor, idempotency_key=body.idempotency_key))
        audit(db, "ACTION_APPROVED", action.id, {"type": action.type, "inspection_id": action.inspection_id}, actor)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "This idempotency key is already in use.") from None
        return action


@router.post("/actions/{action_id}/execute", response_model=ActionOut)
def execute(request: Request, action_id: str, body: IdempotentRequest, actor=Depends(supervisor), db=Depends(database)):
    with request.app.state.mutations:
        action = required(db, CorrectiveAction, action_id)
        if action.status == "EXECUTED":
            if action.execution_key != body.idempotency_key:
                raise HTTPException(409, "Action already executed under a different idempotency key.")
            return action
        inspection, order = validate_action(db, action)
        approval = db.scalar(select(Approval).where(Approval.action_id == action.id))
        if action.status != "APPROVED" or not approval:
            raise HTTPException(409, "Recorded supervisor approval is required before execution.")
        if action.type == "HOLD_ORDER":
            order.status = "HELD"
            inspection.status = "HELD"
            action.execution_details = {"order_held": True, "reinspection_required": True}
        else:
            order.preparation_status = "PICKING_TASK_OPEN"
            action.execution_details = {"task_id": f"pick-{action.id}", "status": "OPEN",
                                        "reinspection_required": True, "inventory_mutated": False}
        action.status = "EXECUTED"
        action.execution_key = body.idempotency_key
        audit(db, "CONTROLLED_ACTION_EXECUTED", action.id, {"type": action.type, **action.execution_details}, actor)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "This execution idempotency key is already in use.") from None
        return action


@router.get("/audit-events", response_model=list[AuditOut])
def audit_events(db=Depends(database)):
    return list(db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(200)))
