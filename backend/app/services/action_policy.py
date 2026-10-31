"""Deterministic boundaries between model recommendations and operational writes."""
from sqlalchemy import select

from backend.app.models.database import AuditEvent, CorrectiveAction, Inspection, Inventory
from backend.app.services.inventory import available_quantity

ACTION_TYPES = {"HOLD_SHIPMENT", "CREATE_PICKING_TASK", "CREATE_REMOVAL_TASK", "REQUEST_REINSPECTION", "ESCALATE_TO_HUMAN"}
UNSAFE_PICKING = {"NOT_OBSERVED", "UNCERTAIN", "UNIDENTIFIED", "GEOMETRY_UNCONFIRMED", "UNCLAIMED_GEOMETRY"}


def evidence_references(db, inspection, order):
    references = {f"order:{order.id}", f"inspection:{inspection.id}", f"photo:{inspection.photo_id}"}
    references.update(f"discrepancy:{row.id}" for row in inspection.discrepancies)
    references.update(f"region:{row['id']}" for row in inspection.regions)
    references.update(f"inventory:{line.product_id}" for line in order.items if db.scalar(
        select(Inventory.id).where(Inventory.product_id == line.product_id)))
    inspection_rows = list(db.scalars(select(Inspection).where(Inspection.order_id == order.id)
        .order_by(Inspection.created_at.desc(), Inspection.id.desc()).limit(20)))
    references.update(f"inspection:{row.id}" for row in inspection_rows)
    references.update(f"photo:{row.photo_id}" for row in inspection_rows)
    inspection_ids = select(Inspection.id).where(Inspection.order_id == order.id)
    action_ids = list(db.scalars(select(CorrectiveAction.id).where(CorrectiveAction.inspection_id.in_(inspection_ids))))
    references.update(f"action:{identifier}" for identifier in action_ids)
    entity_ids = [order.id, *db.scalars(inspection_ids), *action_ids]
    references.update(f"history:{identifier}" for identifier in db.scalars(select(AuditEvent.id).where(
        AuditEvent.entity_id.in_(entity_ids))))
    return references


def supported_shortfall(db, inspection, product_id, quantity):
    if type(quantity) is not int or quantity <= 0:
        return False
    if any(row.type in UNSAFE_PICKING for row in inspection.discrepancies):
        return False
    discrepancy = next((row for row in inspection.discrepancies if row.type == "SHORTFALL"
                        and row.product_id == product_id and row.status == "OPEN"), None)
    if not discrepancy or discrepancy.observed_quantity is None:
        return False
    observations = [row for row in inspection.observations if row.product_id == product_id]
    regions = {row["id"]: row for row in inspection.regions}
    if (not observations or any(row.identification_status != "MATCHED" or not row.count_certain
            or not row.identity_certain or not row.evidence_region_ids or row.quantity is None
            or row.quantity != len(row.evidence_region_ids)
            or any(rid not in regions or regions[rid].get("product_id") != product_id
                   for rid in row.evidence_region_ids) for row in observations)):
        return False
    ids = [rid for row in observations for rid in row.evidence_region_ids]
    return (len(ids) == len(set(ids)) and sum(row.quantity for row in observations) == discrepancy.observed_quantity
            and quantity == discrepancy.required_quantity - discrepancy.observed_quantity
            and available_quantity(db, product_id) >= quantity)


def supported_excess(inspection, product_id, quantity):
    """Require distinct, product-grounded regions for every unit to remove."""
    if type(quantity) is not int or quantity <= 0:
        return False
    discrepancy = next((row for row in inspection.discrepancies if row.type in {"EXCESS", "EXTRA_PRODUCT"}
                        and row.product_id == product_id and row.status == "OPEN"), None)
    if (discrepancy is None or discrepancy.observed_quantity is None
            or discrepancy.required_quantity is None
            or quantity != discrepancy.observed_quantity - discrepancy.required_quantity):
        return False
    observations = [row for row in inspection.observations if row.product_id == product_id]
    regions = {row["id"]: row for row in inspection.regions}
    if (not observations or any(row.identification_status != "MATCHED" or not row.count_certain
            or not row.identity_certain or not row.evidence_region_ids or row.quantity is None
            or row.quantity != len(row.evidence_region_ids)
            or any(rid not in regions or regions[rid].get("product_id") != product_id
                   for rid in row.evidence_region_ids) for row in observations)):
        return False
    ids = [rid for row in observations for rid in row.evidence_region_ids]
    return len(ids) == len(set(ids)) and sum(row.quantity for row in observations) == discrepancy.observed_quantity


def validate_recommendations(db, inspection, order, result):
    """Reject the entire proposal before any action is persisted."""
    if result.get("verification_required") is not True:
        raise ValueError("verification_required")
    if result.get("decision") not in {"CORRECTIVE_ACTION_REQUIRED", "HUMAN_REVIEW_REQUIRED", "NO_ACTION_REQUIRED"}:
        raise ValueError("unsupported_decision")
    if result["decision"] == "NO_ACTION_REQUIRED" and inspection.discrepancies:
        raise ValueError("unresolved_evidence")
    known = evidence_references(db, inspection, order)
    refs = result.get("evidence_references")
    if not isinstance(refs, list) or not refs or any(type(ref) is not str or ref not in known for ref in refs):
        raise ValueError("unsupported_evidence")
    findings = result.get("findings")
    if not isinstance(findings, list) or len(findings) > 100:
        raise ValueError("invalid_findings")
    order_products = {line.product_id for line in order.items}
    observed_products = order_products | {row.product_id for row in inspection.discrepancies if row.product_id}
    finding_types = {"SHORTFALL", "EXCESS", "EXTRA_PRODUCT", "UNIDENTIFIED", "UNCERTAIN", "NOT_OBSERVED", "GEOMETRY_UNCONFIRMED", "OPERATIONAL_CONSTRAINT"}
    for finding in findings:
        if (not isinstance(finding, dict) or finding.get("type") not in finding_types
                or finding.get("product_id") is not None and finding["product_id"] not in observed_products
                or finding.get("quantity") is not None and (type(finding["quantity"]) is not int or finding["quantity"] <= 0)
                or any(ref not in refs for ref in finding.get("evidence_references", []))):
            raise ValueError("unsupported_finding")
        finding_refs = finding.get("evidence_references", [])
        if not finding_refs:
            raise ValueError("unreferenced_finding")
        if finding["type"] == "OPERATIONAL_CONSTRAINT":
            held = (order.status == "HELD" and finding.get("product_id") is None
                    and finding.get("quantity") is None and f"order:{order.id}" in finding_refs)
            shortage = next((row for row in inspection.discrepancies if row.type == "SHORTFALL"
                            and row.product_id == finding.get("product_id") and row.observed_quantity is not None), None)
            insufficient = (finding.get("quantity") is None and shortage is not None
                    and f"inventory:{finding.get('product_id')}" in finding_refs
                    and available_quantity(db, shortage.product_id) < shortage.required_quantity - shortage.observed_quantity)
            if not held and not insufficient:
                raise ValueError("unsupported_constraint")
            continue
        matching = [row for row in inspection.discrepancies if row.product_id == finding.get("product_id")
            and (row.type == finding["type"] or finding["type"] == "EXCESS" and row.type == "EXTRA_PRODUCT")]
        if not matching:
            raise ValueError("unsupported_finding_type")
        discrepancy = next((row for row in matching if f"discrepancy:{row.id}" in finding_refs), None)
        if discrepancy is None:
            raise ValueError("unsupported_finding_reference")
        expected_quantity = None
        if finding["type"] in {"SHORTFALL", "EXCESS", "EXTRA_PRODUCT"}:
            if discrepancy.observed_quantity is None:
                raise ValueError("unsupported_finding_quantity")
            expected_quantity = abs(discrepancy.required_quantity - discrepancy.observed_quantity)
        if finding.get("quantity") != expected_quantity:
            raise ValueError("unsupported_finding_quantity")
    actions = result.get("recommended_actions")
    if not isinstance(actions, list) or not actions or len(actions) > 20:
        raise ValueError("invalid_actions")
    seen = set()
    for action in actions:
        if not isinstance(action, dict) or action.get("type") not in ACTION_TYPES or action.get("requires_approval") is not True:
            raise ValueError("unsupported_action")
        action_refs = action.get("evidence_references")
        if not isinstance(action_refs, list) or not action_refs or any(ref not in refs for ref in action_refs):
            raise ValueError("unsupported_action_evidence")
        product_id, quantity = action.get("product_id"), action.get("quantity")
        if action["type"] == "CREATE_PICKING_TASK":
            discrepancy = next((row for row in inspection.discrepancies if row.type == "SHORTFALL" and row.product_id == product_id), None)
            product_regions = {rid for row in inspection.observations if row.product_id == product_id
                               and row.identification_status == "MATCHED" for rid in row.evidence_region_ids}
            if (product_id not in order_products or not supported_shortfall(db, inspection, product_id, quantity)
                    or result["decision"] != "CORRECTIVE_ACTION_REQUIRED"
                    or f"inventory:{product_id}" not in action_refs
                    or discrepancy is None or f"discrepancy:{discrepancy.id}" not in action_refs
                    or not any(f"region:{rid}" in action_refs for rid in product_regions)):
                raise ValueError("unsupported_picking")
            pending = db.scalar(select(CorrectiveAction.id).join(Inspection).where(Inspection.order_id == order.id,
                CorrectiveAction.type == "CREATE_PICKING_TASK", CorrectiveAction.product_id == product_id,
                CorrectiveAction.status.not_in(["REJECTED", "FAILED"])).limit(1))
            if pending:
                raise ValueError("duplicate_picking")
        elif action["type"] == "CREATE_REMOVAL_TASK":
            discrepancy = next((row for row in inspection.discrepancies if row.type in {"EXCESS", "EXTRA_PRODUCT"}
                                and row.product_id == product_id and row.status == "OPEN"), None)
            product_regions = {rid for row in inspection.observations if row.product_id == product_id
                               and row.identification_status == "MATCHED" for rid in row.evidence_region_ids}
            if (not supported_excess(inspection, product_id, quantity) or discrepancy is None
                    or result["decision"] != "CORRECTIVE_ACTION_REQUIRED"
                    or f"discrepancy:{discrepancy.id}" not in action_refs
                    or not any(f"region:{rid}" in action_refs for rid in product_regions)):
                raise ValueError("unsupported_removal")
            pending = db.scalar(select(CorrectiveAction.id).join(Inspection).where(Inspection.order_id == order.id,
                CorrectiveAction.type == "CREATE_REMOVAL_TASK", CorrectiveAction.product_id == product_id,
                CorrectiveAction.status.not_in(["REJECTED", "FAILED"])).limit(1))
            if pending:
                raise ValueError("duplicate_removal")
        elif product_id is not None or quantity is not None:
            raise ValueError("unexpected_action_parameters")
        key = (action["type"], product_id)
        if key in seen:
            raise ValueError("duplicate_action")
        seen.add(key)
    return actions


def unresolved_escalation(db, order_id):
    return db.scalar(select(CorrectiveAction.id).join(Inspection,
        Inspection.id == CorrectiveAction.inspection_id).where(Inspection.order_id == order_id,
        Inspection.resolved_by_inspection_id.is_(None),
        CorrectiveAction.type == "ESCALATE_TO_HUMAN", CorrectiveAction.status != "REJECTED").limit(1)) is not None
