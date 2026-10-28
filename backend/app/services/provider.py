from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable

from backend.app.services.perception import build_regions, ground_observations
from proofsight.meta_api import MetaConfig, MuseSparkService, SamSegmentationService, create_muse_client, create_sam_client


def run_visual_models(image_path: str, products: list[dict], annotation_path: Path,
                      on_event: Callable[[str, dict], None] | None = None):
    """One Muse scene request followed by at most four actual SAM requests."""
    config = MetaConfig.from_env()
    client = create_muse_client(config)
    if on_event:
        on_event("MUSE_ANALYSIS_STARTED", {"model": config.muse_model})
    try:
        muse = MuseSparkService(client, config.muse_model).inspect_image(image_path, products)
    finally:
        client.close()
    if on_event:
        on_event("MUSE_ANALYSIS_COMPLETED", {key: muse.get(key) for key in
                 ("model", "http_status", "latency_ms", "usage", "ok")})
    if not muse["ok"]:
        return {"muse": muse, "sam": None, "regions": [], "observations": []}

    catalog = {product["id"]: product for product in products}
    candidates = list(dict.fromkeys(row.get("product_id") for row in muse.get("observations", [])
                                   if row.get("product_id") in catalog))
    budget_exceeded = len(candidates) > 4
    requests = [(product_id, catalog[product_id]["description"]) for product_id in candidates[:4]]
    if not requests and products:
        requests = [(None, products[0]["description"])]

    async def segment():
        sam_client = create_sam_client(config)
        results = []
        try:
            service = SamSegmentationService(sam_client, config.sam_model)
            for index, (product_id, description) in enumerate(requests):
                if on_event:
                    on_event("SAM_SEGMENTATION_STARTED", {"product_id": product_id, "model": config.sam_model})
                result = await service.segment(image_path, description, annotation_path if index == 0 else None)
                value = result.as_dict()
                results.append((product_id, value))
                if on_event:
                    on_event("SAM_SEGMENTATION_COMPLETED", {"product_id": product_id, **{key: value.get(key)
                             for key in ("model", "http_status", "latency_ms", "ok")}})
            return results
        finally:
            await sam_client.close()

    runs = asyncio.run(segment()) if requests else []
    failed = next((value for _, value in runs if not value.get("ok")), None)
    error = ({"category": "segmentation_budget_exceeded", "http_status": None} if budget_exceeded else
             failed.get("error") if failed else None)
    if not runs:
        error = {"category": "invalid_catalog", "http_status": None}
    sam = {"ok": bool(runs) and failed is None and not budget_exceeded, "model": config.sam_model,
           "boxes": [{**box, "candidate_product_id": candidate} for candidate, value in runs for box in value.get("boxes", [])],
           "masks": [{**mask, "candidate_product_id": candidate} for candidate, value in runs for mask in value.get("masks", [])],
           "diagnostics": [diagnostic for _, value in runs for diagnostic in value.get("diagnostics", [])],
           "annotated_image": runs[0][1].get("annotated_image") if runs else None,
           "latency_ms": sum(value.get("latency_ms", 0) for _, value in runs),
           "http_status": failed.get("http_status") if failed else 200 if runs else None,
           "error": error, "requests": len(runs)}
    regions = build_regions(runs)
    observations = ground_observations(muse.get("observations", []), regions, products, provider_ok=sam["ok"])
    return {"muse": muse, "sam": sam, "regions": regions, "observations": observations}
