from types import SimpleNamespace

from backend.app.services.evidence_request import reinspection_instructions


def test_unobserved_required_product_requests_visibility_without_claiming_absence():
    inspection = SimpleNamespace(photo_id="photo-before", discrepancies=[SimpleNamespace(
        type="NOT_OBSERVED", product_id="product-yellow", description="Required product was not observed")],
        provider_metadata={})
    order = SimpleNamespace(items=[SimpleNamespace(product_id="product-yellow",
        product=SimpleNamespace(sku="YELLOW-POUCH"))])
    instructions = reinspection_instructions(inspection, order)
    assert "YELLOW-POUCH" in instructions
    assert "complete packing surface" in instructions
    assert "not prove" in instructions
    assert "photo-before" in instructions


def test_uncertain_geometry_and_quality_produce_specific_retakes():
    inspection = SimpleNamespace(photo_id="photo-before", discrepancies=[
        SimpleNamespace(type="UNCERTAIN", product_id=None, description="Uncertain"),
        SimpleNamespace(type="GEOMETRY_UNCONFIRMED", product_id=None, description="No geometry")],
        provider_metadata={"image_quality": {"issues": ["EXCESSIVE_BLUR"]}})
    order = SimpleNamespace(items=[])
    instructions = reinspection_instructions(inspection, order)
    assert "SKU labels readable" in instructions
    assert "Move overlapping items apart" in instructions
    assert "camera steady" in instructions
