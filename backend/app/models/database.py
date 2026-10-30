from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, JSON, String, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def identifier():
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    sku: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    color: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)

    @property
    def reference_image_url(self):
        from backend.app.services.catalog import REFERENCE_CATALOG
        item = REFERENCE_CATALOG.get(self.id)
        return f"/api/products/{self.id}/reference" if item and item["sku"] == self.sku else None

    @property
    def reference_source(self):
        return "original_synthetic_reference" if self.reference_image_url else None


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    reference: Mapped[str] = mapped_column(String, unique=True)
    customer: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="PENDING_INSPECTION")
    preparation_status: Mapped[str] = mapped_column(String, default="READY_FOR_INSPECTION")
    data_source: Mapped[str] = mapped_column(String, default="synthetic_seed")
    shipping_status: Mapped[str] = mapped_column(String, default="NOT_READY")
    requires_reinspection: Mapped[bool] = mapped_column(Boolean, default=False)
    latest_inspection_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=timestamp)
    items: Mapped[list[OrderItem]] = relationship(order_by="OrderItem.id", lazy="selectin")


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (CheckConstraint("quantity > 0"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    product: Mapped[Product] = relationship(lazy="joined")


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (CheckConstraint("quantity_available >= 0"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), unique=True)
    quantity_available: Mapped[int] = mapped_column(Integer)
    location: Mapped[str] = mapped_column(String)


class Inspection(Base):
    __tablename__ = "inspections"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=identifier)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    status: Mapped[str] = mapped_column(String, default="UPLOADED")
    photo_id: Mapped[str] = mapped_column(String, unique=True)
    image_path: Mapped[str] = mapped_column(String)
    image_sha256: Mapped[str] = mapped_column(String)
    image_width: Mapped[int] = mapped_column(Integer, default=0)
    image_height: Mapped[int] = mapped_column(Integer, default=0)
    creation_key: Mapped[str | None] = mapped_column(String, unique=True, index=True, nullable=True)
    processing_stage: Mapped[str] = mapped_column(String, default="IMAGE_RECEIVED")
    reconciliation_status: Mapped[str] = mapped_column(String, default="PENDING_RECONCILIATION")
    comparison: Mapped[list] = mapped_column(JSON, default=list)
    regions: Mapped[list] = mapped_column(JSON, default=list)
    provider_error_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    previous_inspection_id: Mapped[str | None] = mapped_column(ForeignKey("inspections.id"), nullable=True)
    resolved_by_inspection_id: Mapped[str | None] = mapped_column(String, nullable=True)
    provider_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    investigation: Mapped[str | None] = mapped_column(Text, nullable=True)
    investigation_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    investigation_status: Mapped[str] = mapped_column(String, default="NOT_STARTED")
    investigation_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    investigation_error: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    investigation_key: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    investigation_started_at: Mapped[str | None] = mapped_column(String, nullable=True)
    investigation_completed_at: Mapped[str | None] = mapped_column(String, nullable=True)
    segmentations: Mapped[list] = mapped_column(JSON, default=list)
    provider_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String, default=timestamp)
    observations: Mapped[list[InspectionObservation]] = relationship(lazy="selectin", cascade="all, delete-orphan")
    discrepancies: Mapped[list[Discrepancy]] = relationship(lazy="selectin", cascade="all, delete-orphan")
    actions: Mapped[list[CorrectiveAction]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class InspectionObservation(Base):
    __tablename__ = "inspection_observations"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=identifier)
    inspection_id: Mapped[str] = mapped_column(ForeignKey("inspections.id"))
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    label_text: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[str] = mapped_column(Text, default="")
    identity_certain: Mapped[bool] = mapped_column(Boolean, default=False)
    count_certain: Mapped[bool] = mapped_column(Boolean, default=False)
    sku: Mapped[str | None] = mapped_column(String, nullable=True)
    identification_status: Mapped[str] = mapped_column(String, default="UNCERTAIN")
    evidence_region_ids: Mapped[list] = mapped_column(JSON, default=list)


class Discrepancy(Base):
    __tablename__ = "discrepancies"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=identifier)
    inspection_id: Mapped[str] = mapped_column(ForeignKey("inspections.id"))
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    type: Mapped[str] = mapped_column(String)
    required_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    observed_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, default="OPEN")
    description: Mapped[str] = mapped_column(Text)


class CorrectiveAction(Base):
    __tablename__ = "corrective_actions"
    __table_args__ = (CheckConstraint("type IN ('HOLD_ORDER', 'HOLD_SHIPMENT', 'CREATE_PICKING_TASK', 'REQUEST_REINSPECTION', 'ESCALATE_TO_HUMAN')"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=identifier)
    inspection_id: Mapped[str] = mapped_column(ForeignKey("inspections.id"))
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="PROPOSED")
    proposal: Mapped[str] = mapped_column(Text)
    investigation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    evidence_references: Mapped[list] = mapped_column(JSON, default=list)
    lifecycle_state: Mapped[str] = mapped_column(String, default="PROPOSED")
    rejection_key: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    execution_key: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    execution_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=timestamp)


class PickingTask(Base):
    __tablename__ = "picking_tasks"
    __table_args__ = (CheckConstraint("quantity > 0"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=identifier)
    action_id: Mapped[str] = mapped_column(ForeignKey("corrective_actions.id"), unique=True)
    approval_id: Mapped[str] = mapped_column(ForeignKey("approvals.id"))
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    order_reference: Mapped[str] = mapped_column(String)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    product_reference: Mapped[str] = mapped_column(String)
    quantity: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="OPEN")
    created_at: Mapped[str] = mapped_column(String, default=timestamp)


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=identifier)
    action_id: Mapped[str] = mapped_column(ForeignKey("corrective_actions.id"), unique=True)
    operator: Mapped[str] = mapped_column(String)
    idempotency_key: Mapped[str] = mapped_column(String, unique=True)
    created_at: Mapped[str] = mapped_column(String, default=timestamp)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=identifier)
    event_type: Mapped[str] = mapped_column(String)
    entity_id: Mapped[str] = mapped_column(String)
    actor: Mapped[str] = mapped_column(String)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String, default=timestamp)


def connect_database(url):
    engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def configure_sqlite(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=10000")
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def audit(db, event_type, entity_id, details=None, actor="system"):
    db.add(AuditEvent(event_type=event_type, entity_id=entity_id, actor=actor, details=details or {}))
