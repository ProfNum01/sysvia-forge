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
    """
    catalog = {product["id"]: product for product in products}
    proposed: list[str | None] = []
    for row in observations:
        product_id = row.get("product_id")
        product = catalog.get(product_id)
        eligible = (provider_ok and product is not None and row.get("label_text", "").strip() == product["sku"]
                    and row.get("identity_certain") is True and row.get("count_certain") is True
                    and type(row.get("quantity")) is int and row["quantity"] == 1
                    and bool(row.get("evidence", "").strip()) and _valid_box(row.get("source_box")))
        matches = []
        if eligible:
            for region in regions:
                if region["candidate_product_id"] != product_id or _iou(row["source_box"], region["box"]) < 0.5:
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
        result = {**row, "sku": product["sku"] if product else None,
                  "identification_status": "MATCHED" if accepted else "UNCERTAIN" if product else "UNIDENTIFIED",
                  "evidence_region_ids": [region_id] if accepted else [],
                  "identity_certain": accepted, "count_certain": accepted,
                  "quantity": 1 if accepted else None}
        if accepted:
            indexed_regions[region_id]["product_id"] = row["product_id"]
        grounded.append(result)
    return grounded
