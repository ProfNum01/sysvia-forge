from __future__ import annotations

import math
from collections import Counter
from typing import Any

from proofsight.meta_api import SAM_MODEL


def _valid_box(box: Any) -> bool:
    if not isinstance(box, dict):
        return False
    values = [box.get(key) for key in ("left", "top", "right", "bottom")]
    return (all(type(value) in (int, float) and math.isfinite(value) and value >= 0 for value in values)
            and values[0] < values[2] and values[1] < values[3])


def _iou(first: dict, second: dict) -> float:
    if not _valid_box(first) or not _valid_box(second):
        return 0.0
    width = max(0.0, min(first["right"], second["right"]) - max(first["left"], second["left"]))
    height = max(0.0, min(first["bottom"], second["bottom"]) - max(first["top"], second["top"]))
    intersection = width * height
    first_area = (first["right"] - first["left"]) * (first["bottom"] - first["top"])
    second_area = (second["right"] - second["left"]) * (second["bottom"] - second["top"])
    return intersection / (first_area + second_area - intersection)


def _same_unit_location(source: dict, region: dict) -> bool:
    """Associate a shifted scene box only when both boxes share the same column.

    Muse can include the label area while SAM returns the package body. A lower
    IoU is accepted only with strong horizontal alignment and substantial
    vertical overlap; ambiguous multiple candidates remain rejected by caller.
    """
    if _iou(source, region) >= 0.5:
        return True
    horizontal = max(0.0, min(source["right"], region["right"]) - max(source["left"], region["left"]))
    vertical = max(0.0, min(source["bottom"], region["bottom"]) - max(source["top"], region["top"]))
    if _iou(source, region) >= 0.25 and (
            horizontal / min(source["right"] - source["left"], region["right"] - region["left"]) >= 0.65
            and vertical / min(source["bottom"] - source["top"], region["bottom"] - region["top"]) >= 0.75):
        return True
    if _iou(source, region) < 0.4:
        return False
    return (horizontal / min(source["right"] - source["left"], region["right"] - region["left"]) >= 0.85
            and vertical / min(source["bottom"] - source["top"], region["bottom"] - region["top"]) >= 0.6)


def _no_sku_label(product: dict) -> bool:
    """Return True when the product catalog explicitly states no readable SKU label is present."""
    if product.get("no_sku_label"):
        return True
    description = product.get("description", "")
    return "no visible sku label" in description.lower()


def build_regions(sam_runs: list[tuple[str | None, dict]]) -> list[dict]:
    """Keep actual SAM geometry; a prompt identifies a candidate, never a product.

    Near-identical detections are represented once. Conflicting product prompts
    lose even their candidate assignment. The retained box is an actual SAM box,
    never an average or a box supplied by Muse.
    """
    regions: list[dict] = []
    for candidate_id, result in sam_runs:
        if not result.get("ok") or result.get("model") != SAM_MODEL:
            continue
        masks = {str(mask["object_id"]): mask for mask in result.get("masks", [])}
        for record in result.get("boxes", []):
            box = {key: record.get(key) for key in ("left", "top", "right", "bottom")}
            if not _valid_box(box):
                continue
            duplicate = next((region for region in regions if _iou(region["box"], box) >= 0.8), None)
            if duplicate is not None:
                if duplicate["candidate_product_id"] != candidate_id:
                    duplicate["candidate_product_id"] = None
                continue
            object_id = str(record["object_id"])
            mask = masks.get(object_id)
            regions.append({
                "id": f"region-{candidate_id or 'unknown'}-{object_id}", "object_id": object_id,
                "source": SAM_MODEL, "box": box, "candidate_product_id": candidate_id, "product_id": None,
                "mask": {key: mask[key] for key in ("svg_path", "width", "height", "bounds")}
                if mask and all(key in mask for key in ("svg_path", "width", "height", "bounds")) else None,
            })
    return regions


def ground_observations(observations: list[dict], regions: list[dict], products: list[dict],
                        provider_ok: bool = True) -> list[dict]:
    """Accept individually labelled units only after unique scene/SAM agreement.

    IoU >= 0.5 is an association threshold, not a confidence score. Aggregate
    claims without per-unit locations stay uncertain. Multiple claims to one
    region invalidate every claimant instead of accepting the first row.

    For products with no visible SKU label (flagged via ``no_sku_label`` or the
    seed description convention "no visible SKU label"), visual candidate matching
    is used instead of SKU label matching.  The region's ``candidate_product_id``
    must match the observation's ``visual_candidate_product_id`` and the region
    must be uncontested.  This is a weaker signal than label identity; it is used
    only when the catalog explicitly declares that no label is present.
    """
    catalog = {product["id"]: product for product in products}
    proposed: list[str | None] = []
    for row in observations:
        product_id = row.get("product_id")
        visual_cand = row.get("visual_candidate_product_id")
        product = catalog.get(product_id)
        no_sku = product is not None and _no_sku_label(product)

        # ── Standard SKU-label path ──────────────────────────────────────────
        eligible = (provider_ok and product is not None
                    and not no_sku
                    and row.get("label_text", "").strip() == product["sku"]
                    and row.get("identity_certain") is True and row.get("count_certain") is True
                    and type(row.get("quantity")) is int and row["quantity"] == 1
                    and bool(row.get("evidence", "").strip()) and _valid_box(row.get("source_box")))

        # ── Visual-candidate path for no-SKU-label products ──────────────────
        # Accepted when:
        #   1. The catalog product has no visible SKU label.
        #   2. Muse reported visual_candidate_product_id matching this product.
        #   3. Muse reported a non-empty visual_evidence description.
        #   4. Muse reported a non-empty evidence/reasoning text.
        #   5. A valid source_box was supplied so we can IoU-match SAM regions.
        #   6. quantity == 1 (per-unit only).
        visual_eligible = (not eligible and provider_ok and product is not None
                           and no_sku
                           and visual_cand == product_id
                           and bool(row.get("visual_evidence", "").strip())
                           and bool(row.get("evidence", "").strip())
                           and _valid_box(row.get("source_box"))
                           and type(row.get("quantity")) is int and row.get("quantity") == 1)

        matches = []
        if eligible:
            for region in regions:
                if region["candidate_product_id"] != product_id or not _same_unit_location(row["source_box"], region["box"]):
                    continue
                conflicts = any(other["id"] != region["id"] and other["candidate_product_id"] != product_id
                                and _iou(region["box"], other["box"]) >= 0.5 for other in regions)
                if not conflicts:
                    matches.append(region["id"])
        elif visual_eligible:
            # For visual-candidate matching the region must have been prompted with
            # this product's candidate id (from the SAM run).
            for region in regions:
                if region["candidate_product_id"] != product_id:
                    continue
                if not _same_unit_location(row["source_box"], region["box"]):
                    continue
                conflicts = any(other["id"] != region["id"] and other["candidate_product_id"] != product_id
                                and _iou(region["box"], other["box"]) >= 0.5 for other in regions)
                if not conflicts:
                    matches.append(region["id"])
        proposed.append(matches[0] if len(matches) == 1 else None)
    claims = Counter(region_id for region_id in proposed if region_id is not None)
    indexed_regions = {region["id"]: region for region in regions}
    for region in regions:
        region["product_id"] = None
    grounded = []
    for row, region_id in zip(observations, proposed):
        accepted = region_id is not None and claims[region_id] == 1
        product = catalog.get(row.get("product_id"))
        no_sku = product is not None and _no_sku_label(product)
        # Build evidence text; annotate visual-only matches for transparency.
        evidence_text = row.get("evidence", "")
        if accepted and no_sku and not (row.get("label_text", "").strip() == (product["sku"] if product else "")):
            visual_note = f"[visual-only: no SKU label on product] {evidence_text}".strip()
        else:
            visual_note = evidence_text
        result = {**row, "sku": product["sku"] if product else None,
                  "identification_status": "MATCHED" if accepted else "UNCERTAIN" if product else "UNIDENTIFIED",
                  "evidence_region_ids": [region_id] if accepted else [],
                  "identity_certain": accepted, "count_certain": accepted,
                  "quantity": 1 if accepted else None,
                  "evidence": visual_note}
        if accepted:
            indexed_regions[region_id]["product_id"] = row["product_id"]
        grounded.append(result)
    return grounded
