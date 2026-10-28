from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class FromORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProductOut(FromORM):
    id: str
    sku: str
    name: str
    color: str
    description: str
    reference_image_url: str | None = None
    reference_source: str | None = None


class PixelBox(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    left: float = Field(ge=0)
    top: float = Field(ge=0)
    right: float = Field(gt=0)
    bottom: float = Field(gt=0)

    @model_validator(mode="after")
    def ordered(self):
        if self.right <= self.left or self.bottom <= self.top:
            raise ValueError("Box must have positive area")
        return self


class RegionMask(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    svg_path: str = Field(max_length=2_000_000, pattern=r"^[MmLlHhVvZzCcSsQqTtAaEe0-9., +\-\r\n]*$")
    width: int = Field(gt=0, le=20000)
    height: int = Field(gt=0, le=20000)
    bounds: PixelBox


class EvidenceRegion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(min_length=1, max_length=180, pattern=r"^[a-zA-Z0-9_.:-]+$")
    object_id: str = Field(min_length=1, max_length=100)
    source: Literal["sam-3.1"]
    box: PixelBox
    candidate_product_id: str | None
    product_id: str | None
    mask: RegionMask | None


class ObservationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    product_id: str | None
    quantity: int | None = Field(ge=1, le=10000)
    label_text: str = Field(max_length=500)
    evidence: str = Field(max_length=4000)
    identity_certain: bool
    count_certain: bool
    sku: str | None = None
    identification_status: Literal["MATCHED", "UNCERTAIN", "UNIDENTIFIED"] = "UNCERTAIN"
    evidence_region_ids: list[str] = Field(default_factory=list, max_length=100)
    source_box: PixelBox | None = None


class ComparisonOut(BaseModel):
    product_id: str
    sku: str
    name: str
    required_quantity: int
    observed_quantity: int | None
    difference: int | None
    status: str
    evidence_region_ids: list[str]


class ProviderErrorOut(BaseModel):
    category: str
    http_status: int | None
    retryable: bool


class ItemOut(FromORM):
    id: str
    product_id: str
    quantity: int
    product: ProductOut


class OrderOut(FromORM):
    id: str
    reference: str
    customer: str
    status: str
    preparation_status: str
    data_source: str
    latest_inspection_id: str | None
    created_at: str
    items: list[ItemOut]


class ObservationOut(FromORM):
    id: str
    product_id: str | None
    quantity: int | None
    label_text: str
    evidence: str
    identity_certain: bool
    count_certain: bool
    sku: str | None
    identification_status: Literal["MATCHED", "UNCERTAIN", "UNIDENTIFIED"]
    evidence_region_ids: list[str]


class DiscrepancyOut(FromORM):
    id: str
    product_id: str | None
    type: str
    required_quantity: int | None
    observed_quantity: int | None
    status: str
    description: str


class ActionOut(FromORM):
    id: str
    inspection_id: str
    product_id: str | None
    quantity: int | None
    type: str
    status: str
    proposal: str
    execution_details: dict | None


class InspectionOut(FromORM):
    id: str
    order_id: str
    status: str
    photo_id: str
    previous_inspection_id: str | None
    resolved_by_inspection_id: str | None
    created_at: str
    provider_error: str | None
    investigation: str | None
    observations: list[ObservationOut]
    discrepancies: list[DiscrepancyOut]
    actions: list[ActionOut]
    segmentations: list[dict]
    image_width: int
    image_height: int
    processing_stage: str
    reconciliation_status: str
    comparison: list[ComparisonOut]
    regions: list[EvidenceRegion]
    provider_metadata: dict
    provider_error_details: ProviderErrorOut | None
    execution_events: list[AuditOut] = Field(default_factory=list)
    unidentified_objects: list[ObservationOut] = Field(default_factory=list)
    image_url: str = ""
    annotation_url: str | None = None


class AuditOut(FromORM):
    id: str
    event_type: str
    entity_id: str
    actor: str
    created_at: str
    details: dict[str, Any]


class HealthOut(BaseModel):
    status: str
    database: str


class LiveCheckOut(BaseModel):
    checked_at: str
    model: str
    http_status: int
    latency_ms: int
    usage: dict[str, int]
    requests: int


class MetaStatusOut(BaseModel):
    configured: bool
    base_url: str
    muse_model: str
    sam_model: str
    operator_auth_configured: bool
    configuration_location: str
    last_live_check: str | None
    last_live_result: LiveCheckOut | None
    note: str


class DashboardOut(BaseModel):
    total_orders: int
    pending_inspections: int
    verified_orders: int
    active_discrepancies: int
    order_status_distribution: list[dict]
    recent_inspections: list[InspectionOut]
    agent_activity: list[AuditOut]
    data_source: str = "synthetic_seed"


class IdempotentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=8, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
