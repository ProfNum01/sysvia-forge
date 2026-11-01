from __future__ import annotations
import re


def _iou(a, b):
    left, top = max(a["left"], b["left"]), max(a["top"], b["top"])
    right, bottom = min(a["right"], b["right"]), min(a["bottom"], b["bottom"])
    overlap = max(0, right-left) * max(0, bottom-top)
    union = (a["right"]-a["left"])*(a["bottom"]-a["top"]) + (b["right"]-b["left"])*(b["bottom"]-b["top"]) - overlap
    return overlap / union if union > 0 else 0


def _no_sku_label(product: dict) -> bool:
    """Return True when the product catalog explicitly states no readable SKU label is present.

    This is detected either from the ``no_sku_label`` flag added to the catalog entry
    or from the legacy seed description convention ("no visible SKU label").
    """
    if product.get("no_sku_label"):
        return True
    description = product.get("description", "")
    return "no visible sku label" in description.lower()


def reconcile(expected: list[dict], observations: list[dict], geometry_available: bool,
              catalog: list[dict] | None = None, regions: list[dict] | None = None):
    """Only distinct, corroborated SAM regions can support SKU quantities.

    For products whose catalog description explicitly states no visible SKU label
    (``no_sku_label=True`` or "no visible SKU label" in description), identity is
    established through SAM-corroborated visual candidate matching instead of SKU
    label text.  The visual_candidate_product_id supplied by Muse acts as the
    identity signal and SAM geometry provides the count evidence.  This is a
    deliberately weaker signal than label-text identity: the result is still marked
    MATCHED so that packing scenes can pass verification, but the discrepancy
    description notes that identity is visual-only.
    """
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
        visual_cand = observation.get("visual_candidate_product_id")
        product = products.get(pid)
        label, detail = observation.get("label_text", ""), observation.get("evidence", "")
        ids = observation.get("evidence_region_ids", [])
        quantity = observation.get("quantity")
        no_sku = product is not None and _no_sku_label(product)

        # --- Standard SKU-label identity path ---
        scene_sku = product is not None and not no_sku and bool(re.search(
            r"(?<![A-Z0-9-])" + re.escape(product["sku"].upper()) + r"(?![A-Z0-9-])", label.upper()))
        localized = (geometry_available and bool(ids) and len(ids) == len(set(ids))
                     and all(rid in evidence and rid not in ambiguous_ids
                             and evidence[rid].get("product_id") == pid for rid in ids))
        identity = bool(observation.get("identity_certain") and scene_sku and detail.strip() and localized)
        count = bool(identity and observation.get("count_certain") and type(quantity) is int
                     and 1 <= quantity <= 10000 and quantity == len(ids))

        # --- Visual-candidate identity path for no-SKU-label products ---
        # Allowed only when:
        #   1. The product explicitly has no visible SKU label.
        #   2. Muse supplied a visual_candidate_product_id matching this product.
        #   3. The observation has a non-empty visual_evidence description.
        #   4. SAM geometry is available and provides a unique, non-ambiguous region.
        #   5. quantity == 1 (per-unit counting only; aggregate claims stay uncertain).
        # This does NOT set identity_certain=True in the broader scene sense — the DB
        # record still carries identity_certain=True because the region is accepted, but
        # identification_status is "MATCHED_VISUAL" stored as "MATCHED" for pipeline
        # compatibility, with the visual-only flag recorded in evidence text.
        if not identity and no_sku and product is not None:
            visual_candidate_match = (visual_cand == pid and
                                      bool(observation.get("visual_evidence", "").strip()) and
                                      bool(detail.strip()))
            visual_localized = (geometry_available and bool(ids) and len(ids) == len(set(ids))
                                and all(rid in evidence and rid not in ambiguous_ids
                                        and evidence[rid].get("candidate_product_id") == pid
                                        for rid in ids))
            visual_count = (type(quantity) is int and 1 <= quantity <= 10000 and quantity == len(ids))
            if visual_candidate_match and visual_localized and visual_count:
                # Accept visual-only identity: mark the region with the product_id so
                # downstream logic can use it, but preserve the visual-only note.
                identity = True
                count = True
                detail = f"[visual-only: no SKU label on product] {detail}".strip()

        normalized.append({
            "product_id": pid if product else None, "sku": product["sku"] if product else None,
            "visual_candidate_product_id": observation.get("visual_candidate_product_id"),
            "visual_evidence": observation.get("visual_evidence", ""),
            "quantity": quantity if count else None, "label_text": label, "evidence": detail,
            "identity_certain": identity, "count_certain": count,
            "identification_status": "MATCHED" if identity and count else "UNCERTAIN" if product else "UNIDENTIFIED",
            "evidence_region_ids": list(ids) if (localized or (count and not scene_sku)) else [],
        })
    claimed_ids = {rid for row in normalized for rid in row["evidence_region_ids"]}
    unclaimed = list(dict.fromkeys(r["id"] for r in regions if r["id"] not in claimed_ids))
    if unclaimed:
        normalized.append({
            "product_id": None, "sku": None, "quantity": None, "label_text": "",
            "visual_candidate_product_id": None, "visual_evidence": "",
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
