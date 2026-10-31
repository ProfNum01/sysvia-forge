from __future__ import annotations

import hmac
import json
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
    InspectionObservation, Inventory, Order, PickingTask, RemovalTask, Product, audit, identifier, timestamp)
from backend.app.core.config import ROOT
from backend.app.schemas.responses import (ActionOut, AuditOut, DashboardOut, HealthOut, IdempotentRequest,
    EvidenceRegion, InspectionOut, MetaStatusOut, ObservationInput, OrderOut, ProductOut, RejectionRequest, ShippingRequest)
from backend.app.services.action_policy import supported_excess, supported_shortfall, unresolved_escalation, validate_recommendations
from backend.app.services.catalog import reference_path
from backend.app.services.investigation import investigate_with_read_tools
from backend.app.services.inventory import available_quantity
from backend.app.services.media import prepare_image
from backend.app.services.provider import run_visual_models
from backend.app.services.reconciliation import reconcile
from proofsight.meta_api import MetaConfig, MetaConfigurationError, classify_api_error

router = APIRouter(prefix="/api")
DEMO_ASSETS = {
    "missing": ("Visible shortfall", "One red and one blue package in an original synthetic scene."),
    "correct": ("Required visible count", "Two red and one blue package in an original synthetic scene."),
    "extra": ("Additional product", "Two red, one blue, and one green package in an original synthetic scene."),
    "ambiguous": ("Unreadable label", "A product label is deliberately unreadable in an original synthetic scene."),
    "unidentified": ("Unidentified shape", "An additional unidentified object appears in an original synthetic scene."),
}


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
            AuditEvent.entity_id.in_([inspection.id, *[action.id for action in inspection.actions]])
            ).order_by(AuditEvent.created_at, AuditEvent.id)))
    output.unidentified_objects = [o for o in output.observations if o.identification_status == "UNIDENTIFIED"]
    return output


def require_current(db, inspection):
    order = required(db, Order, inspection.order_id)
    if order.latest_inspection_id != inspection.id:
        raise HTTPException(409, "A newer inspection exists. This evidence and its actions are superseded.")
    db.refresh(order)
    for item in order.items:
        db.refresh(item)
        db.refresh(item.product)
    if (inspection.requirements_revision != order.requirements_revision
            or inspection.order_version != order.version):
        raise HTTPException(409, "Order requirements changed. Submit new evidence for the current revision.")
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


@router.get("/demo/assets")
def demo_assets():
    folder = ROOT / "data" / "fixtures"
    return [{"name": name, "title": title, "description": description,
             "provenance": "original_synthetic_fixture", "url": f"/api/demo/assets/{name}"}
            for name, (title, description) in DEMO_ASSETS.items()
            if (folder / f"task002-{name}.png").is_file()]


@router.get("/demo/assets/{name}")
def demo_asset(name: str):
    if name not in DEMO_ASSETS:
        raise HTTPException(404, "Demo asset was not found.")
    path = ROOT / "data" / "fixtures" / f"task002-{name}.png"
    if not path.is_file():
        raise HTTPException(404, "Demo asset is unavailable on this installation.")
    return FileResponse(path, media_type="image/png", headers={
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


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
    orders = list(db.scalars(select(Order).order_by(Order.reference)))
    states = Counter(order.status for order in orders)
    attention = []
    human_review = 0
    uncertain_types = {"NOT_OBSERVED", "UNCERTAIN", "UNIDENTIFIED", "GEOMETRY_UNCONFIRMED"}
    for order in orders:
        current = db.get(Inspection, order.latest_inspection_id) if order.latest_inspection_id else None
        issues = sorted({row.type for row in current.discrepancies if row.status == "OPEN"}) if current else []
        needs_review = bool(current and (any(item in uncertain_types for item in issues)
            or any(action.type == "ESCALATE_TO_HUMAN" and action.status not in {"REJECTED", "SUPERSEDED"}
                   for action in current.actions)))
        human_review += int(needs_review)
        if current and (issues or order.shipping_status == "HELD" or order.requires_reinspection):
            attention.append({"order_id": order.id, "order_reference": order.reference,
                "inspection_id": current.id, "inspection_status": current.status,
                "shipping_status": order.shipping_status, "requires_reinspection": order.requires_reinspection,
                "issue_types": issues, "human_review_required": needs_review})
    return {
        "total_orders": sum(states.values()), "pending_inspections": sum(v for k, v in states.items() if k != "VERIFIED"),
        "verified_orders": states["VERIFIED"],
        "orders_on_hold": sum(order.shipping_status == "HELD" for order in orders),
        "pending_human_reviews": human_review,
        "attention_required": attention[:8],
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
    if order.shipping_status == "SHIPPED":
        raise HTTPException(409, "A shipped order cannot accept replacement inspection evidence.")
    if order.latest_inspection_id:
        latest = required(db, Inspection, order.latest_inspection_id)
        if latest.status == "ANALYZING":
            raise HTTPException(409, "The current inspection is being analyzed.")
        if latest.investigation_status == "RUNNING":
            raise HTTPException(409, "The current inspection is being investigated. Wait for the bounded investigation to finish.")
        if parent is None:
            raise HTTPException(409, "Use reinspection to attach new evidence to the existing inspection chain.")
        if latest.id != parent.id:
            raise HTTPException(409, "Reinspection must use the latest inspection.")
    if parent is not None and parent.status in {"UPLOADED", "ANALYZING"}:
        raise HTTPException(409, "Analyze the current image before requesting reinspection.")
    if parent is not None and any(action.investigation_id and action.status != "EXECUTED"
                                  for action in parent.actions):
        raise HTTPException(409, "Approve and execute pending corrective actions before reinspection.")
    if parent is not None and db.scalar(select(PickingTask.id).where(
            PickingTask.order_id == order.id, PickingTask.status != "COMPLETED").limit(1)):
        raise HTTPException(409, "Report physical picking completion before submitting new evidence.")
    if parent is not None and db.scalar(select(RemovalTask.id).where(
            RemovalTask.order_id == order.id, RemovalTask.status != "COMPLETED").limit(1)):
        raise HTTPException(409, "Report physical removal completion before submitting new evidence.")
    if parent:
        prior = parent
        while prior:
            if prior.image_sha256 == digest:
                raise HTTPException(409, "New visual evidence is required. This image matches an earlier photo.")
            prior = db.get(Inspection, prior.previous_inspection_id) if prior.previous_inspection_id else None
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    inspection = Inspection(order_id=order.id, requirements_revision=order.requirements_revision,
                            order_version=order.version,
                            photo_id=photo_id, image_path=str(destination),
                            image_sha256=digest, image_width=width, image_height=height, creation_key=creation_key,
                            processing_stage="IMAGE_VALIDATED", previous_inspection_id=parent.id if parent else None)
    try:
        db.add(inspection)
        db.flush()
        order.latest_inspection_id = inspection.id
        if parent:
            for action in parent.actions:
                if action.investigation_id is None and action.status == "PROPOSED":
                    action.status = "SUPERSEDED"
                    action.lifecycle_state = "SUPERSEDED"
                    audit(db, "AUTOMATIC_HOLD_SUPERSEDED", action.id,
                          {"new_inspection_id": inspection.id, "new_photo_id": inspection.photo_id})
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


def inspection_chain(db, inspection):
    chain = []
    while inspection:
        chain.append(inspection)
        inspection = db.get(Inspection, inspection.previous_inspection_id) if inspection.previous_inspection_id else None
    return list(reversed(chain))


@router.get("/inspections/{inspection_id}/evidence", response_model=list[InspectionOut])
def inspection_evidence(inspection_id: str, actor=Depends(supervisor), db=Depends(database)):
    return [inspection_out(row) for row in inspection_chain(db, required(db, Inspection, inspection_id))]


@router.get("/inspections/{inspection_id}/comparison")
def inspection_comparison(inspection_id: str, actor=Depends(supervisor), db=Depends(database)):
    chain = inspection_chain(db, required(db, Inspection, inspection_id))
    return {"order_id": chain[-1].order_id,
            "before": inspection_out(chain[0]), "after": inspection_out(chain[-1]),
            "history_ids": [row.id for row in chain]}


@router.get("/orders/{order_id}/verification-status")
def verification_status(order_id: str, actor=Depends(supervisor), db=Depends(database)):
    order = required(db, Order, order_id)
    current = db.get(Inspection, order.latest_inspection_id) if order.latest_inspection_id else None
    revision_current = bool(current and current.requirements_revision == order.requirements_revision
                            and current.order_version == order.version)
    tasks = list(db.scalars(select(PickingTask).where(PickingTask.order_id == order_id)
        .order_by(PickingTask.created_at, PickingTask.id)))
    removal_tasks = list(db.scalars(select(RemovalTask).where(RemovalTask.order_id == order_id)
        .order_by(RemovalTask.created_at, RemovalTask.id)))
    return {"order_id": order.id, "inspection_id": current.id if current else None,
            "verification_status": ("STALE_ORDER" if current and not revision_current else
                                    current.status if current else "AWAITING_EVIDENCE"),
            "requirements_revision": order.requirements_revision,
            "order_version": order.version,
            "inspection_revision": current.requirements_revision if current else None,
            "inspection_order_version": current.order_version if current else None,
            "revision_current": revision_current,
            "picking_tasks": [{"id": task.id, "product_id": task.product_id,
                               "quantity": task.quantity, "status": task.status} for task in tasks],
            "removal_tasks": [{"id": task.id, "product_id": task.product_id,
                               "quantity": task.quantity, "status": task.status} for task in removal_tasks],
            "reconciliation_status": current.reconciliation_status if current else None,
            "requires_reinspection": order.requires_reinspection,
            "shipping_status": order.shipping_status}


@router.get("/orders/{order_id}/verification-history", response_model=list[InspectionOut])
def verification_history(order_id: str, actor=Depends(supervisor), db=Depends(database)):
    required(db, Order, order_id)
    return [inspection_out(row) for row in db.scalars(select(Inspection).where(
        Inspection.order_id == order_id).order_by(Inspection.created_at, Inspection.id))]


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
    prior_ids = []
    prior = db.get(Inspection, inspection.previous_inspection_id) if inspection.previous_inspection_id else None
    while prior:
        prior_ids.append(prior.id)
        prior = db.get(Inspection, prior.previous_inspection_id) if prior.previous_inspection_id else None
    unresolved_actions = list(db.scalars(select(CorrectiveAction).where(
        CorrectiveAction.inspection_id.in_(prior_ids),
        CorrectiveAction.status.not_in(["EXECUTED", "SUPERSEDED"])))) if prior_ids else []
    open_picking = list(db.scalars(select(PickingTask).where(
        PickingTask.order_id == order.id, PickingTask.status != "COMPLETED")))
    open_removal = list(db.scalars(select(RemovalTask).where(
        RemovalTask.order_id == order.id, RemovalTask.status != "COMPLETED")))
    eligible = reconciliation["verified"] and not unresolved_actions and not open_picking and not open_removal
    if eligible:
        claimed = db.execute(update(Order).where(Order.id == order.id,
            Order.version == inspection.order_version,
            Order.latest_inspection_id == inspection.id).values(status="VERIFIED"))
        if not claimed.rowcount:
            db.rollback()
            raise HTTPException(409, "Order requirements changed during verification.")
        inspection.status = "VERIFIED"
        order.preparation_status = "VERIFIED_BY_NEW_EVIDENCE"
        order.requires_reinspection = False
        order.shipping_status = "NOT_READY"
        prior = db.get(Inspection, inspection.previous_inspection_id) if inspection.previous_inspection_id else None
        while prior:
            prior.resolved_by_inspection_id = inspection.id
            for discrepancy in prior.discrepancies:
                discrepancy.status = "RESOLVED"
            for action in prior.actions:
                if action.status == "EXECUTED" and action.lifecycle_state == "AWAITING_REINSPECTION":
                    action.lifecycle_state = "RESOLVED_BY_REINSPECTION"
                    action.execution_details = {**(action.execution_details or {}),
                        "reinspection_required": False, "resolved_by_inspection_id": inspection.id,
                        "resolved_by_photo_id": inspection.photo_id, "previous_photo_id": prior.photo_id}
                    audit(db, "ACTION_RESOLVED_BY_REINSPECTION", inspection.id,
                        {"action_id": action.id, "previous_photo_id": prior.photo_id, "new_photo_id": inspection.photo_id})
            prior = db.get(Inspection, prior.previous_inspection_id) if prior.previous_inspection_id else None
        db.flush()
        if unresolved_escalation(db, order.id):
            order.status = "HELD"
            order.shipping_status = "HELD"
        audit(db, "EVIDENCE_RECONCILED", inspection.id, {"photo_id": inspection.photo_id,
              "previous_inspection_id": inspection.previous_inspection_id})
    else:
        inspection.status = "NEEDS_REVIEW"
        order.requires_reinspection = True
        order.shipping_status = "HELD"
        if order.status != "HELD":
            order.status = "NEEDS_REVIEW"
        if reconciliation["discrepancies"]:
            db.add(CorrectiveAction(inspection_id=inspection.id, type="HOLD_ORDER",
                                   proposal="Hold this order for human review. Visual evidence has unresolved discrepancies."))
            audit(db, "DISCREPANCIES_DETECTED", inspection.id, {"count": len(reconciliation["discrepancies"])})
        else:
            audit(db, "VERIFICATION_BLOCKED", inspection.id,
                  {"pending_action_ids": [a.id for a in unresolved_actions],
                   "open_picking_task_ids": [task.id for task in open_picking]})
            if open_removal:
                audit(db, "REMOVAL_TASKS_OPEN", inspection.id,
                      {"task_ids": [task.id for task in open_removal]})
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
def investigate(request: Request, inspection_id: str,
                idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
                actor=Depends(supervisor), db=Depends(database)):
    with request.app.state.mutations:
        inspection = required(db, Inspection, inspection_id)
        order = require_current(db, inspection)
        if inspection.status not in {"NEEDS_REVIEW", "HELD"}:
            raise HTTPException(409, "Investigation requires analyzed, unresolved evidence.")
        if idempotency_key is not None:
            if not re.fullmatch(r"[a-zA-Z0-9_-]{8,100}", idempotency_key):
                raise HTTPException(422, "Invalid investigation idempotency key.")
            owner = db.scalar(select(Inspection).where(Inspection.investigation_key == idempotency_key))
            if owner is not None and owner.id != inspection.id:
                raise HTTPException(409, "This investigation idempotency key belongs to another inspection.")
        if inspection.investigation_status in {"RUNNING", "COMPLETED"}:
            return inspection_out(inspection)
        attempt = timestamp()
        changed = db.execute(update(Inspection).where(Inspection.id == inspection.id,
            Inspection.investigation_status.in_(["NOT_STARTED", "FAILED"])).values(
                investigation_id=inspection.investigation_id or identifier(),
                investigation_key=idempotency_key or inspection.investigation_key,
                investigation_status="RUNNING", investigation_error=None,
                investigation_started_at=attempt, investigation_completed_at=None))
        if not changed.rowcount:
            db.rollback()
            db.expire_all()
            return inspection_out(required(db, Inspection, inspection_id))
        audit(db, "INVESTIGATION_STARTED", inspection.id, {"investigation_id": inspection.investigation_id}, actor)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "This investigation idempotency key belongs to another request.") from None

    def event(stage, details):
        if stage not in {"TOOL_CALLED", "TOOL_COMPLETED", "EVIDENCE_RETRIEVED", "AGENT_MODEL_STARTED", "AGENT_MODEL_COMPLETED", "VALIDATION_FAILED"}:
            raise ValueError("unsupported_investigation_event")
        allowed = {"tool", "arguments", "result", "evidence_references", "order_id", "inspection_id", "product_id",
                   "model", "http_status", "latency_ms", "usage", "ok", "request_index", "category", "status",
                   "reason", "validation_stage", "candidate"}
        safe = {key: value for key, value in details.items() if key in allowed}
        if len(json.dumps(safe, ensure_ascii=True)) > 20000:
            raise ValueError("oversized_investigation_event")
        with request.app.state.mutations, request.app.state.sessions() as progress:
            current = progress.get(Inspection, inspection_id)
            current_order = progress.get(Order, current.order_id)
            if (current.investigation_status == "RUNNING" and current.investigation_started_at == attempt
                    and current_order.latest_inspection_id == current.id):
                audit(progress, stage, current.id, {**safe, "investigation_id": current.investigation_id}, "meta-read-tool")
                progress.commit()

    def failed(category, message, status, retryable=False, validation=False, reason=None):
        with request.app.state.mutations:
            db.expire_all()
            current = required(db, Inspection, inspection_id)
            require_current(db, current)
            if current.investigation_status != "RUNNING" or current.investigation_started_at != attempt:
                raise HTTPException(409, "Investigation was interrupted or superseded.")
            current.investigation_status = "FAILED"
            current.investigation_error = {"category": category, "message": message, "retryable": retryable}
            if reason in {"invalid_agent_decision", "unsupported_evidence", "unsupported_finding", "unsupported_action", "unsupported_decision"}:
                current.investigation_error = {**current.investigation_error, "reason": reason}
            current.investigation_completed_at = timestamp()
            audit(db, "VALIDATION_FAILED" if validation else "INVESTIGATION_FAILED", current.id,
                  {"category": category, "investigation_id": current.investigation_id,
                   "reason": current.investigation_error.get("reason")})
            db.commit()
        raise HTTPException(status, message)

    try:
        summary = investigate_with_read_tools(db, inspection, order, on_event=event)
    except MetaConfigurationError:
        return failed("configuration", "MODEL_API_KEY is missing. Configure the root .env file.", 503)
    except ValueError as exc:
        return failed("invalid_recommendation", "The agent returned an unsupported recommendation or tool request. No action was created.", 422,
                      validation=True, reason=getattr(exc, "safe_reason", None))
    except Exception as exc:
        error = getattr(exc, "safe_error", None) or classify_api_error(exc)
        category = error["category"]
        return failed(category, "Meta investigation failed. No corrective action was executed.",
                      504 if category == "timeout" else 429 if category == "rate_limit" else 503 if category == "connection" else 502,
                      retryable=category in {"timeout", "rate_limit", "connection", "service_error"})
    with request.app.state.mutations:
        db.expire_all()
        inspection = required(db, Inspection, inspection_id)
        order = require_current(db, inspection)
        if inspection.investigation_status != "RUNNING" or inspection.investigation_started_at != attempt:
            raise HTTPException(409, "Investigation was interrupted or superseded. No actions were applied.")
        try:
            result = summary.model_dump()
            proposals = validate_recommendations(db, inspection, order, result)
        except (ValueError, TypeError, AttributeError, KeyError):
            return failed("invalid_recommendation", "The proposed actions are not supported by current database evidence. No action was created.", 422, validation=True)
        inspection.investigation = result["summary"]
        inspection.investigation_result = result
        inspection.investigation_status = "COMPLETED"
        inspection.investigation_completed_at = timestamp()
        for proposal in proposals:
            equivalent_types = {"HOLD_ORDER", "HOLD_SHIPMENT"} if proposal["type"] == "HOLD_SHIPMENT" else {proposal["type"]}
            duplicate = next((action for action in inspection.actions if action.type in equivalent_types
                and action.product_id == proposal.get("product_id") and action.quantity == proposal.get("quantity")
                and action.status != "REJECTED"), None)
            if duplicate:
                duplicate.investigation_id = inspection.investigation_id
                duplicate.evidence_references = proposal["evidence_references"]
                continue
            action = CorrectiveAction(inspection_id=inspection.id, investigation_id=inspection.investigation_id,
                type=proposal["type"], product_id=proposal.get("product_id"), quantity=proposal.get("quantity"),
                proposal=result["summary"], evidence_references=proposal["evidence_references"],
                status="PENDING_APPROVAL", lifecycle_state="PENDING_APPROVAL")
            db.add(action)
            db.flush()
            audit(db, "ACTION_PROPOSED", inspection.id, {"action_id": action.id, "type": action.type,
                "investigation_id": inspection.investigation_id})
            audit(db, "APPROVAL_REQUIRED", inspection.id, {"action_id": action.id, "type": action.type})
        audit(db, "INVESTIGATION_COMPLETED", inspection.id, {"investigation_id": inspection.investigation_id,
              "decision": result["decision"], "write_operations": 0}, actor="meta-read-tool")
        db.commit()
        db.refresh(inspection)
        return inspection_out(inspection)


def validate_action(db, action):
    inspection = required(db, Inspection, action.inspection_id)
    order = require_current(db, inspection)
    if order.shipping_status == "SHIPPED":
        raise HTTPException(409, "A shipped order cannot execute corrective operations.")
    if inspection.status not in {"NEEDS_REVIEW", "HELD"}:
        raise HTTPException(409, "This evidence no longer supports a corrective action.")
    if action.type == "CREATE_PICKING_TASK":
        if not inspection.investigation or not supported_shortfall(db, inspection, action.product_id, action.quantity):
            raise HTTPException(409, "Current evidence and inventory do not authorize this picking task.")
    elif action.type == "CREATE_REMOVAL_TASK":
        if not inspection.investigation or not supported_excess(inspection, action.product_id, action.quantity):
            raise HTTPException(409, "Current evidence does not authorize this removal task.")
    elif action.type not in {"HOLD_ORDER", "HOLD_SHIPMENT", "REQUEST_REINSPECTION", "ESCALATE_TO_HUMAN"}:
        raise HTTPException(422, "Action type is not permitted by deterministic policy.")
    return inspection, order


@router.post("/actions/{action_id}/approve", response_model=ActionOut)
def approve(request: Request, action_id: str, body: IdempotentRequest, actor=Depends(supervisor), db=Depends(database)):
    with request.app.state.mutations:
        action = required(db, CorrectiveAction, action_id)
        existing = db.scalar(select(Approval).where(Approval.action_id == action.id))
        if existing:
            if existing.idempotency_key != body.idempotency_key:
                raise HTTPException(409, "Action already has an approval under a different idempotency key.")
            return action
        validate_action(db, action)
        if action.status not in {"PROPOSED", "PENDING_APPROVAL"}:
            raise HTTPException(409, "Only a proposed action can be approved.")
        action.status = "APPROVED"
        action.lifecycle_state = "APPROVED"
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
        approval = db.scalar(select(Approval).where(Approval.action_id == action.id))
        if action.status != "APPROVED" or not approval:
            raise HTTPException(409, "Recorded supervisor approval is required before execution.")
        try:
            changed = db.execute(update(CorrectiveAction).where(CorrectiveAction.id == action.id,
                CorrectiveAction.status == "APPROVED").values(status="EXECUTING", lifecycle_state="EXECUTING"))
            if not changed.rowcount:
                raise HTTPException(409, "Another request has claimed this action.")
            # Revalidate after the write claim, within the same transaction as stock reservation.
            db.expire_all()
            action = required(db, CorrectiveAction, action_id)
            inspection, order = validate_action(db, action)
            order.requires_reinspection = True
            order.shipping_status = "HELD"
            if action.type in {"HOLD_ORDER", "HOLD_SHIPMENT"}:
                order.status = "HELD"
                inspection.status = "HELD"
                action.execution_details = {"order_id": order.id, "order_held": True, "reinspection_required": True}
            elif action.type == "CREATE_PICKING_TASK":
                product = required(db, Product, action.product_id)
                task = PickingTask(id=f"pick-{action.id}", action_id=action.id, approval_id=approval.id,
                    order_id=order.id, order_reference=order.reference, product_id=product.id,
                    product_reference=product.sku, quantity=action.quantity, status="OPEN")
                db.add(task)
                db.flush()
                order.preparation_status = "PICKING_TASK_OPEN"
                action.execution_details = {"task_id": task.id, "status": task.status,
                    "order_id": task.order_id, "order_reference": task.order_reference, "product_id": task.product_id,
                    "product_reference": task.product_reference, "quantity": task.quantity, "created_at": task.created_at,
                    "approval_id": task.approval_id, "reinspection_required": True, "inventory_mutated": False}
            elif action.type == "CREATE_REMOVAL_TASK":
                product = required(db, Product, action.product_id)
                task = RemovalTask(id=f"remove-{action.id}", action_id=action.id, approval_id=approval.id,
                    order_id=order.id, order_reference=order.reference, product_id=product.id,
                    product_reference=product.sku, quantity=action.quantity, status="OPEN")
                db.add(task)
                db.flush()
                order.preparation_status = "REMOVAL_TASK_OPEN"
                action.execution_details = {"task_id": task.id, "status": task.status,
                    "order_id": task.order_id, "order_reference": task.order_reference,
                    "product_id": task.product_id, "product_reference": task.product_reference,
                    "quantity": task.quantity, "created_at": task.created_at,
                    "approval_id": task.approval_id, "reinspection_required": True, "inventory_mutated": False,
                    "required_product_review_ids": sorted({row.product_id for row in inspection.discrepancies
                        if row.type == "NOT_OBSERVED" and row.product_id}),
                    "replacement_decision": "OPERATOR_MUST_CONFIRM"}
            elif action.type == "REQUEST_REINSPECTION":
                order.preparation_status = "NEW_EVIDENCE_REQUIRED"
                action.execution_details = {"order_id": order.id, "previous_photo_id": inspection.photo_id,
                    "reinspection_required": True, "status": "AWAITING_NEW_PHOTO"}
            else:
                order.status = "HELD"
                action.execution_details = {"order_id": order.id, "human_review_required": True,
                    "status": "PENDING_HUMAN_REVIEW", "reinspection_required": True}
            action.status = "EXECUTED"
            action.lifecycle_state = "AWAITING_REINSPECTION"
            action.execution_key = body.idempotency_key
            action.error_details = None
            audit(db, "CONTROLLED_ACTION_EXECUTED", action.id, {"type": action.type, **action.execution_details}, actor)
            audit(db, "EXECUTION_COMPLETED", inspection.id, {"action_id": action.id, "type": action.type}, actor)
            audit(db, "REINSPECTION_REQUIRED", inspection.id, {"action_id": action.id, "previous_photo_id": inspection.photo_id})
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "This execution idempotency key is already in use.") from None
        except HTTPException:
            db.rollback()
            action = required(db, CorrectiveAction, action_id)
            if action.status == "APPROVED":
                action.status = "FAILED"
                action.lifecycle_state = "FAILED"
                action.error_details = {"category": "policy_validation", "message": "Current evidence or stock no longer supports execution."}
                audit(db, "EXECUTION_FAILED", action.inspection_id, {"action_id": action.id, "category": "policy_validation"})
                db.commit()
            raise
        except Exception:
            db.rollback()
            action = required(db, CorrectiveAction, action_id)
            action.status = "FAILED"
            action.lifecycle_state = "FAILED"
            action.error_details = {"category": "transaction_failed", "message": "Execution failed. No partial operational change was retained."}
            audit(db, "EXECUTION_FAILED", action.inspection_id, {"action_id": action.id, "category": "transaction_failed"})
            db.commit()
            raise HTTPException(500, action.error_details["message"]) from None
        return action


@router.post("/actions/{action_id}/reject", response_model=ActionOut)
def reject(request: Request, action_id: str, body: RejectionRequest, actor=Depends(supervisor), db=Depends(database)):
    with request.app.state.mutations:
        action = required(db, CorrectiveAction, action_id)
        if action.status == "REJECTED":
            if action.rejection_key != body.idempotency_key or action.rejection_reason != body.reason:
                raise HTTPException(409, "This rejection belongs to a different request.")
            return action
        if action.status not in {"PROPOSED", "PENDING_APPROVAL"}:
            raise HTTPException(409, "Only an action awaiting approval can be rejected.")
        action.status = "REJECTED"
        action.lifecycle_state = "REJECTED"
        action.rejection_key = body.idempotency_key
        action.rejection_reason = body.reason
        audit(db, "ACTION_REJECTED", action.inspection_id, {"action_id": action.id, "type": action.type}, actor)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "This rejection idempotency key is already in use.") from None
        return action


@router.post("/picking-tasks/{task_id}/complete")
def complete_picking_task(request: Request, task_id: str, body: IdempotentRequest,
                          actor=Depends(supervisor), db=Depends(database)):
    with request.app.state.mutations:
        task = required(db, PickingTask, task_id)
        if task.status == "COMPLETED":
            prior = db.scalar(select(AuditEvent).where(AuditEvent.event_type == "PICKING_TASK_COMPLETED",
                AuditEvent.entity_id == task.id))
            if prior and prior.details.get("idempotency_key") == body.idempotency_key:
                return {"id": task.id, "status": task.status, "order_id": task.order_id}
            raise HTTPException(409, "Picking task was completed by a different request.")
        if task.status != "OPEN":
            raise HTTPException(409, "Only an open picking task can be completed.")
        task.status = "COMPLETED"
        audit(db, "PICKING_TASK_COMPLETED", task.id,
              {"order_id": task.order_id, "idempotency_key": body.idempotency_key,
               "physical_completion_reported": True, "visual_verification": False}, actor)
        db.commit()
        return {"id": task.id, "status": task.status, "order_id": task.order_id}


@router.post("/removal-tasks/{task_id}/complete")
def complete_removal_task(request: Request, task_id: str, body: IdempotentRequest,
                          actor=Depends(supervisor), db=Depends(database)):
    with request.app.state.mutations:
        task = required(db, RemovalTask, task_id)
        if task.status == "COMPLETED":
            prior = db.scalar(select(AuditEvent).where(AuditEvent.event_type == "REMOVAL_TASK_COMPLETED",
                AuditEvent.entity_id == task.id))
            if prior and prior.details.get("idempotency_key") == body.idempotency_key:
                return {"id": task.id, "status": task.status, "order_id": task.order_id}
            raise HTTPException(409, "Removal task was completed by a different request.")
        if task.status != "OPEN":
            raise HTTPException(409, "Only an open removal task can be completed.")
        task.status = "COMPLETED"
        audit(db, "REMOVAL_TASK_COMPLETED", task.id,
              {"order_id": task.order_id, "idempotency_key": body.idempotency_key,
               "physical_completion_reported": True, "visual_verification": False}, actor)
        db.commit()
        return {"id": task.id, "status": task.status, "order_id": task.order_id}


@router.post("/orders/{order_id}/shipping-transition", response_model=OrderOut)
def shipping_transition(request: Request, order_id: str, body: ShippingRequest, actor=Depends(supervisor), db=Depends(database)):
    with request.app.state.mutations:
        order = required(db, Order, order_id)
        prior = db.scalar(select(AuditEvent).where(AuditEvent.event_type == "SHIPPING_TRANSITION",
            AuditEvent.entity_id == order.id, AuditEvent.details["idempotency_key"].as_string() == body.idempotency_key))
        if prior:
            if prior.details.get("target") != body.target:
                raise HTTPException(409, "This shipping request already used a different target.")
            return order
        inspection = required(db, Inspection, order.latest_inspection_id) if order.latest_inspection_id else None
        if (not inspection or inspection.order_version != order.version
                or inspection.requirements_revision != order.requirements_revision
                or inspection.status != "VERIFIED" or order.status != "VERIFIED"
                or order.requires_reinspection or order.shipping_status == "HELD" or unresolved_escalation(db, order.id)):
            raise HTTPException(409, "Shipping requires a verified current photo and resolved operational holds.")
        if body.target == "SHIPPED" and order.shipping_status != "READY_TO_SHIP":
            raise HTTPException(409, "The verified order must be shipping-ready before it can be shipped.")
        if order.shipping_status == "SHIPPED":
            raise HTTPException(409, "A shipped order cannot transition backwards.")
        order.shipping_status = body.target
        audit(db, "SHIPPING_TRANSITION", order.id, {"target": body.target, "idempotency_key": body.idempotency_key}, actor)
        db.commit()
        return order


@router.get("/audit-events", response_model=list[AuditOut])
def audit_events(db=Depends(database)):
    return list(db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(200)))
