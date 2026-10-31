export type Product = {
  id: string;
  sku: string;
  name: string;
  color?: string;
  description?: string;
  reference_image_url?: string | null;
  reference_source?: "original_synthetic_reference" | null;
};
export type Order = {
  id: string;
  version: number;
  requirements_revision: string;
  reference: string;
  customer: string;
  status: string;
  preparation_status: string;
  data_source: string;
  latest_inspection_id: string | null;
  shipping_status?: string;
  requires_reinspection?: boolean;
  created_at: string;
  items: {
    id: string;
    product_id: string;
    quantity: number;
    product: Product;
  }[];
};
export type VerificationStatus = {
  order_id: string;
  verification_status: string;
  revision_current: boolean;
  requires_reinspection: boolean;
  shipping_status: string;
  picking_tasks: { id: string; product_id: string; quantity: number; status: string }[];
  removal_tasks: { id: string; product_id: string; quantity: number; status: string }[];
};
export type Observation = {
  id: string;
  product_id?: string;
  quantity?: number;
  label_text?: string;
  evidence: string;
  identity_certain: boolean;
  count_certain: boolean;
  sku?: string | null;
  identification_status?: "MATCHED" | "UNCERTAIN" | "UNIDENTIFIED";
  evidence_region_ids?: string[];
};
export type Discrepancy = {
  id: string;
  product_id?: string;
  type: string;
  required_quantity?: number;
  observed_quantity?: number;
  status: string;
  description: string;
};
export type Action = {
  id: string;
  type: string;
  status: string;
  proposal: string | Record<string, unknown>;
  product_id?: string;
  quantity?: number;
  inspection_id: string;
  order_id?: string;
  order_reference?: string;
  investigation_id?: string | null;
  evidence_references?: string[];
  error_details?: { category?: string; message?: string } | null;
  lifecycle_state?: string;
  execution_details?: Record<string, unknown> | null;
  rejection_reason?: string | null;
};
export type InvestigationResult = {
  investigation_id?: string;
  inspection_id?: string;
  decision?: string;
  summary?: string;
  findings?: {
    type?: string;
    product_id?: string | null;
    quantity?: number | null;
    description?: string;
    evidence?: string;
    evidence_references?: string[];
    [key: string]: unknown;
  }[];
  evidence_references?: string[];
  recommended_actions?: Record<string, unknown>[];
  verification_required?: boolean;
};
export type Inspection = {
  id: string;
  order_version?: number | null;
  requirements_revision?: string | null;
  order_id: string;
  status: string;
  photo_id: string;
  previous_inspection_id?: string | null;
  resolved_by_inspection_id?: string | null;
  created_at: string;
  provider_error?: string | null;
  observations: Observation[];
  discrepancies: Discrepancy[];
  actions: Action[];
  image_url?: string;
  investigation?: string | null;
  investigation_id?: string | null;
  investigation_status?: "NOT_STARTED" | "RUNNING" | "COMPLETED" | "FAILED";
  investigation_result?: InvestigationResult | null;
  investigation_error?: {
    category: string;
    message: string;
    retryable: boolean;
  } | null;
  investigation_started_at?: string | null;
  investigation_completed_at?: string | null;
  annotation_url?: string | null;
  segmentations?: unknown[];
  image_width?: number;
  image_height?: number;
  processing_stage?: string;
  reconciliation_status?:
    | "PENDING_RECONCILIATION"
    | "MISMATCH_DETECTED"
    | "NEEDS_REVIEW"
    | "VERIFIED";
  provider_metadata?: {
    muse_model?: string;
    muse_usage?: unknown;
    muse_latency_ms?: number;
    sam_latency_ms?: number;
    sam_model?: string;
    total_latency_ms?: number;
  };
  execution_events?: {
    id: string;
    event_type: string;
    created_at: string;
    details: Record<string, unknown>;
  }[];
  regions?: EvidenceRegion[];
  comparison?: ProductComparisonRow[];
  unidentified_objects?: Observation[];
  provider_error_details?: {
    category: string;
    http_status: number | null;
    retryable: boolean;
  } | null;
};
export type EvidenceRegion = {
  id: string;
  object_id: string | number;
  source: "sam-3.1";
  box: { left: number; top: number; right: number; bottom: number };
  candidate_product_id: string | null;
  product_id: string | null;
  mask: {
    svg_path: string;
    width: number;
    height: number;
    bounds: { left: number; top: number; right: number; bottom: number };
  } | null;
};
export type ProductComparisonRow = {
  product_id: string;
  sku: string;
  name: string;
  required_quantity: number;
  observed_quantity: number | null;
  difference: number | null;
  status: string;
  evidence_region_ids: string[];
};
export type Audit = {
  id: string;
  event_type: string;
  entity_id: string;
  actor: string;
  created_at: string;
  details: unknown;
};
export type Summary = {
  total_orders: number;
  pending_inspections: number;
  verified_orders: number;
  active_discrepancies: number;
  orders_on_hold: number;
  pending_human_reviews: number;
  attention_required: {
    order_id: string;
    order_reference: string;
    inspection_id: string;
    inspection_status: string;
    shipping_status: string;
    requires_reinspection: boolean;
    issue_types: string[];
    human_review_required: boolean;
  }[];
  order_status_distribution: { status: string; count: number }[];
  recent_inspections: Inspection[];
  agent_activity: Audit[];
};
export type MetaStatus = {
  configured: boolean;
  base_url: string;
  muse_model: string;
  sam_model: string;
  last_live_check: string | null;
  operator_auth_configured: boolean;
  configuration_location?: string;
};
export type DemoAsset = {
  name: string;
  title: string;
  description: string;
  provenance: "original_synthetic_fixture";
  url: string;
};
