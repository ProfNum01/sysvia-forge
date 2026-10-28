"""Explicitly mocked perception fixtures; never evidence of live model inference."""

from __future__ import annotations


def grounded_visual_result(red_quantity=2, *, certain=True):
    """Return distinct per-unit regions contained in the tests' 32x32 images."""
    raw_observations, observations, regions, boxes = [], [], [], []
    units = [("product-red", "PS-RED-01")] * red_quantity + [("product-blue", "PS-BLUE-02")]
    for index, (product_id, sku) in enumerate(units):
        left, top = 1 + (index % 4) * 8, 1 + (index // 4) * 8
        box = {"left": left, "top": top, "right": left + 6, "bottom": top + 6}
        object_id, region_id = f"unit-{index+1}", f"region-{index+1}"
        raw = {"product_id": product_id if certain else None,
               "quantity": 1 if certain else None, "label_text": sku if certain else "Unreadable label",
               "evidence": "Mock fixture: one distinctly visible unit with its own readable SKU label."
                           if certain else "Mock fixture: object identity and count are ambiguous.",
               "identity_certain": certain, "count_certain": certain,
               "source_box": box.copy(), "evidence_region_ids": []}
        raw_observations.append(raw)
        observations.append({**raw, "sku": sku if certain else None,
                             "identification_status": "MATCHED" if certain else "UNCERTAIN",
                             "evidence_region_ids": [region_id]})
        boxes.append({"object_id": object_id, **box, "confidence": None})
        regions.append({"id": region_id, "object_id": object_id, "source": "sam-3.1", "box": box.copy(),
                        "candidate_product_id": product_id, "product_id": product_id if certain else None,
                        "mask": None})
    return {"muse": {"ok": True, "model": "muse-spark-1.3", "usage": None, "latency_ms": 1,
                     "observations": raw_observations},
            "sam": {"ok": True, "model": "sam-3.1", "latency_ms": 1, "boxes": boxes,
                    "masks": [], "diagnostics": [], "annotated_image": None},
            "observations": observations, "regions": regions}
