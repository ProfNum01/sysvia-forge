from __future__ import annotations
import re


def _iou(a, b):
    left, top = max(a["left"], b["left"]), max(a["top"], b["top"])
    right, bottom = min(a["right"], b["right"]), min(a["bottom"], b["bottom"])
    overlap = max(0, right-left) * max(0, bottom-top)
    union = (a["right"]-a["left"])*(a["bottom"]-a["top"]) + (b["right"]-b["left"])*(b["bottom"]-b["top"]) - overlap
    return overlap / union if union > 0 else 0


def reconcile(expected: list[dict], observations: list[dict], geometry_available: bool,
              catalog: list[dict] | None = None, regions: list[dict] | None = None):
    """Only distinct, corroborated SAM regions can support SKU quantities."""
    catalog = catalog if catalog is not None else expected
    products = {p.get("id", p.get("product_id")): p for p in catalog}
    expected_ids = {p["product_id"] for p in expected}
    regions = regions or []
    evidence = {r["id"]: r for r in regions}
    ambiguous_ids = {r["id"] for r in regions if sum(x["id"] == r["id"] for x in regions) != 1}
    for index, region in enumerate(regions):
        for other in regions[index+1:]:
            if _iou(region["box"], other["box"]) >= 0.5:
                ambiguous_ids.update((region["id"], other["id"]))
    claims = {}
    for index, observation in enumerate(observations):
        for region_id in observation.get("evidence_region_ids", []):
            claims.setdefault(region_id, set()).add(index)
    ambiguous_ids.update(rid for rid, owners in claims.items() if len(owners) > 1)
    normalized = []
    for observation in observations:
        pid = observation.get("product_id")
        product = products.get(pid)
        label, detail = observation.get("label_text", ""), observation.get("evidence", "")
        ids = observation.get("evidence_region_ids", [])
        quantity = observation.get("quantity")
        scene_sku = product is not None and bool(re.search(
            r"(?<![A-Z0-9-])" + re.escape(product["sku"].upper()) + r"(?![A-Z0-9-])", label.upper()))
        localized = (geometry_available and bool(ids) and len(ids) == len(set(ids))
                     and all(rid in evidence and rid not in ambiguous_ids
                             and evidence[rid].get("product_id") == pid for rid in ids))
        identity = bool(observation.get("identity_certain") and scene_sku and detail.strip() and localized)
        count = bool(identity and observation.get("count_certain") and type(quantity) is int
                     and 1 <= quantity <= 10000 and quantity == len(ids))
        normalized.append({
            "product_id": pid if product else None, "sku": product["sku"] if product else None,
            "quantity": quantity if count else None, "label_text": label, "evidence": detail,
            "identity_certain": identity, "count_certain": count,
            "identification_status": "MATCHED" if identity and count else "UNCERTAIN" if product else "UNIDENTIFIED",
            "evidence_region_ids": list(ids) if localized else [],
        })
    claimed_ids = {rid for row in normalized for rid in row["evidence_region_ids"]}
    unclaimed = list(dict.fromkeys(r["id"] for r in regions if r["id"] not in claimed_ids))
    if unclaimed:
        normalized.append({
            "product_id": None, "sku": None, "quantity": None, "label_text": "",
            "evidence": "SAM returned unmatched visual regions. Their product identity and quantity are not established.",
            "identity_certain": False, "count_certain": False, "identification_status": "UNIDENTIFIED",
            "evidence_region_ids": unclaimed,
        })
    comparison, discrepancies = [], []
    rows = [dict(item) for item in expected]
    for pid in dict.fromkeys(o["product_id"] for o in normalized if o["product_id"] not in expected_ids and o["product_id"]):
        product = products[pid]
        rows.append({"product_id": pid, "sku": product["sku"], "name": product.get("name", product["sku"]), "quantity": 0})
    for item in rows:
        matches = [o for o in normalized if o["product_id"] == item["product_id"]]
        known_count = bool(matches) and all(o["identification_status"] == "MATCHED" for o in matches)
        qty = sum(o["quantity"] for o in matches) if known_count else None
        difference = qty-item["quantity"] if qty is not None else None
        ids = [rid for o in matches for rid in o["evidence_region_ids"]]
        if not matches:
            kind, description = "NOT_OBSERVED", "Required product was not observed; this does not prove it is absent."
        elif not known_count:
            kind, description = "UNCERTAIN", "Scene identity, quantity, or distinct SAM evidence is insufficient. Human review required."
        elif item["quantity"] == 0:
            kind, description = "EXTRA_PRODUCT", f"Catalog product is not required by this order; {qty} supported visible unit(s)."
        elif difference == 0:
            kind, description = "MATCHED", ""
        else:
            kind = "SHORTFALL" if difference < 0 else "EXCESS"
            description = f"Evidence supports {qty} visible unit(s) against {item['quantity']} required. Review the supporting regions."
        comparison.append({"product_id": item["product_id"], "sku": item["sku"],
            "name": item.get("name", products.get(item["product_id"], {}).get("name", item["sku"])),
            "required_quantity": item["quantity"], "observed_quantity": qty, "difference": difference,
            "status": kind, "evidence_region_ids": ids})
        if kind != "MATCHED":
            discrepancies.append({"product_id": item["product_id"], "type": kind,
                "required_quantity": item["quantity"], "observed_quantity": qty, "description": description})
    if any(o["identification_status"] == "UNIDENTIFIED" for o in normalized):
        discrepancies.append({"product_id": None, "type": "UNIDENTIFIED", "required_quantity": None,
                              "observed_quantity": None, "description": "Unidentified objects require human review."})
    if not geometry_available:
        discrepancies.append({"product_id": None, "type": "GEOMETRY_UNCONFIRMED", "required_quantity": None,
                              "observed_quantity": None, "description": "SAM returned no accepted geometry; visual evidence remains unconfirmed."})
    verified = bool(expected) and not discrepancies
    mismatch = any(d["type"] in {"SHORTFALL", "EXCESS", "EXTRA_PRODUCT"} for d in discrepancies)
    return {"verified": verified, "observations": normalized, "discrepancies": discrepancies,
            "comparison": comparison,
            "reconciliation_status": "VERIFIED" if verified else "MISMATCH_DETECTED" if mismatch else "NEEDS_REVIEW"}
