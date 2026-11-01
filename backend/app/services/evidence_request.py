"""Ground reinspection instructions in recorded uncertainty, without asserting absence."""

from backend.app.services.image_quality import GUIDANCE


def reinspection_instructions(inspection, order) -> str:
    sku_by_product = {item.product_id: item.product.sku for item in order.items}
    steps = []
    for discrepancy in inspection.discrepancies:
        if discrepancy.type == "NOT_OBSERVED":
            sku = sku_by_product.get(discrepancy.product_id, "the required product")
            steps.append(f"Reveal {sku} and capture the complete packing surface, including obscured areas. Not observed does not prove absence.")
        elif discrepancy.type == "UNCERTAIN":
            steps.append("Move items apart and make SKU labels readable in a closer, well-lit view.")
        elif discrepancy.type == "UNIDENTIFIED":
            steps.append("Capture another angle showing the unidentified object's full shape and readable label, if present.")
        elif discrepancy.type == "GEOMETRY_UNCONFIRMED":
            steps.append("Move overlapping items apart and capture distinct object boundaries from another angle.")
    quality = (inspection.provider_metadata or {}).get("image_quality", {})
    for issue in quality.get("issues", []):
        if issue in GUIDANCE:
            steps.append(GUIDANCE[issue])
    if not steps:
        steps.append("Capture a distinct photo showing the complete packing surface and readable product labels.")
    return (f"Photo {inspection.photo_id} leaves visual evidence unresolved. "
            + " ".join(dict.fromkeys(steps))
            + " Submit a new rights-cleared photo, then run independent Meta analysis. "
              "Do not treat task completion as order verification.")
