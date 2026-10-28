import { useState } from "react";
import {
  Activity,
  Eye,
  EyeOff,
  Focus,
  ImageOff,
  ScanLine,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { Button } from "./ui/button";
import {
  comparisonValue,
  maskTransform,
  modelEventStatus,
  regionLabel,
  sourceBox,
} from "../lib/evidence";
import { formatTime, label } from "../lib/api";
import type {
  EvidenceRegion,
  Inspection,
  Product,
  ProductComparisonRow,
} from "../types";

export function EvidenceViewer({
  inspection,
  products,
  selectedRegionIds,
  onSelectRegion,
}: {
  inspection: Inspection;
  products: Product[];
  selectedRegionIds: string[];
  onSelectRegion: (ids: string[]) => void;
}) {
  const [zoom, setZoom] = useState(1);
  const [overlays, setOverlays] = useState(true);
  const [masks, setMasks] = useState(true);
  const [imageError, setImageError] = useState(false);
  const width = inspection.image_width;
  const height = inspection.image_height;
  const dimensionsKnown =
    width != null && height != null && width > 0 && height > 0;
  const regions = (inspection.regions ?? []).filter((region) =>
    sourceBox(region.box),
  );
  const maskCount = regions.filter(
    (region) => region.mask?.svg_path && maskTransform(region.mask),
  ).length;
  function Region({ region }: { region: EvidenceRegion }) {
    const box = sourceBox(region.box)!;
    const selected = selectedRegionIds.includes(region.id);
    const name = regionLabel(region, products);
    const fontSize = Math.max(12, width! / 62);
    const labelWidth = Math.min(
      width! - box.x,
      (name.length + 4) * fontSize * 0.65,
    );
    const labelY = Math.max(0, box.y - fontSize * 1.65);
    const transform = region.mask ? maskTransform(region.mask) : null;
    return (
      <g
        className={`evidence-region ${selected ? "region-selected" : ""} ${name === "UNIDENTIFIED" ? "region-unidentified" : ""}`}
        role="button"
        tabIndex={0}
        aria-label={`${name}, SAM object ${region.object_id}, ${region.mask ? "mask available" : "bounding box"}`}
        aria-pressed={selected}
        onClick={() => onSelectRegion(selected ? [] : [region.id])}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onSelectRegion(selected ? [] : [region.id]);
          }
        }}
      >
        <title>
          {name} · Region {region.id} · Source: {region.source}
        </title>
        {overlays && (
          <>
            {masks && region.mask?.svg_path && transform && (
              <path
                className="evidence-mask"
                d={region.mask.svg_path}
                transform={transform}
                vectorEffect="non-scaling-stroke"
              />
            )}
            <rect
              className="evidence-box"
              {...box}
              vectorEffect="non-scaling-stroke"
            />
            <rect
              className="evidence-label-background"
              x={box.x}
              y={labelY}
              width={labelWidth}
              height={fontSize * 1.6}
              rx={2}
            />
            <text
              className="evidence-label"
              x={box.x + fontSize * 0.3}
              y={labelY + fontSize * 1.15}
              fontSize={fontSize}
            >
              {name}
            </text>
          </>
        )}
      </g>
    );
  }
  return (
    <div className="evidence-viewer">
      <div className="viewer-toolbar" aria-label="Evidence image controls">
        <span className="viewer-source">
          <ScanLine size={14} aria-hidden="true" />
          Original evidence{dimensionsKnown ? ` · ${width} × ${height} px` : ""}
        </span>
        <div className="viewer-controls">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Zoom out"
            disabled={zoom <= 1}
            onClick={() => setZoom((value) => Math.max(1, value - 0.25))}
          >
            <ZoomOut size={16} />
          </Button>
          <output aria-label="Image zoom" className="viewer-zoom">
            {Math.round(zoom * 100)}%
          </output>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Zoom in"
            disabled={zoom >= 3}
            onClick={() => setZoom((value) => Math.min(3, value + 0.25))}
          >
            <ZoomIn size={16} />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Reset image zoom"
            onClick={() => setZoom(1)}
          >
            <Focus size={16} />
          </Button>
          <Button
            variant="outline"
            size="sm"
            aria-pressed={overlays}
            disabled={!dimensionsKnown || !regions.length}
            onClick={() => setOverlays((value) => !value)}
          >
            {overlays ? (
              <Eye size={14} aria-hidden="true" />
            ) : (
              <EyeOff size={14} aria-hidden="true" />
            )}
            {overlays ? "Hide overlays" : "Show overlays"}
          </Button>
        </div>
      </div>
      <div
        className="evidence-canvas"
        tabIndex={0}
        role="region"
        aria-label="Scrollable original inspection image and evidence overlays"
      >
        {!inspection.image_url || imageError ? (
          <div className="viewer-empty">
            <ImageOff size={25} aria-hidden="true" />
            <p>
              Original image unavailable. The evidence record remains preserved.
            </p>
          </div>
        ) : dimensionsKnown ? (
          <svg
            className="source-image-svg"
            viewBox={`0 0 ${width} ${height}`}
            width={width}
            height={height}
            style={{ width: `${zoom * 100}%` }}
            aria-label="Original uploaded image with actual SAM source-coordinate regions"
          >
            <image
              href={inspection.image_url}
              x="0"
              y="0"
              width={width}
              height={height}
              preserveAspectRatio="none"
              onError={() => setImageError(true)}
            />
            {overlays &&
              regions.map((region) => (
                <Region key={region.id} region={region} />
              ))}
          </svg>
        ) : (
          <img
            src={inspection.image_url}
            alt={`Original uploaded evidence for inspection ${inspection.id}`}
            style={{ width: `${zoom * 100}%`, maxWidth: "none" }}
            onError={() => setImageError(true)}
          />
        )}
      </div>
      <div className="viewer-evidence-caption">
        <p>
          {dimensionsKnown
            ? `${regions.length} geometry region${regions.length === 1 ? "" : "s"} recorded by SAM. Geometry does not independently establish SKU or item quantity.`
            : "Source dimensions are unavailable for this historical record. Overlays are withheld to avoid misaligned evidence."}
        </p>
        {!!maskCount && (
          <label className="viewer-mask-toggle">
            <input
              type="checkbox"
              checked={masks}
              onChange={(event) => setMasks(event.target.checked)}
              disabled={!overlays}
            />
            Show actual masks ({maskCount})
          </label>
        )}
        {!!selectedRegionIds.length && (
          <Button variant="ghost" size="sm" onClick={() => onSelectRegion([])}>
            Clear evidence selection
          </Button>
        )}
      </div>
      {!!regions.length && (
        <div className="region-list" aria-label="Actual segmentation regions">
          {regions.map((region) => (
            <button
              type="button"
              key={region.id}
              aria-pressed={selectedRegionIds.includes(region.id)}
              className={`region-chip ${selectedRegionIds.includes(region.id) ? "selected" : ""}`}
              onClick={() => {
                setOverlays(true);
                onSelectRegion(
                  selectedRegionIds.includes(region.id) ? [] : [region.id],
                );
              }}
            >
              <span
                className={
                  region.product_id
                    ? "associated-region-dot"
                    : "unidentified-region-dot"
                }
              />
              {regionLabel(region, products)}
              <span>Object {region.object_id}</span>
            </button>
          ))}
        </div>
      )}
      {!regions.length && (
        <p className="form-hint">
          No renderable SAM regions are recorded for this inspection. No
          overlays have been substituted.
        </p>
      )}
    </div>
  );
}

export function ProductComparison({
  rows,
  selectedRegionIds,
  onSelectRegions,
}: {
  rows: ProductComparisonRow[];
  selectedRegionIds: string[];
  onSelectRegions: (ids: string[]) => void;
}) {
  return (
    <div className="table-wrap comparison-table">
      <table>
        <caption>
          Deterministic comparison from the backend. Unknown evidence is never
          treated as zero.
        </caption>
        <thead>
          <tr>
            <th>Product</th>
            <th>Required</th>
            <th>Observed</th>
            <th>Difference</th>
            <th>Status</th>
            <th>Evidence</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.product_id}
              className={`${row.evidence_region_ids.some((id) => selectedRegionIds.includes(id)) ? "comparison-selected" : ""} ${row.status === "MISMATCH_DETECTED" || (row.difference != null && row.difference !== 0) ? "comparison-discrepancy" : ""}`}
            >
              <td>
                <strong>{row.name}</strong>
                <span className="cell-subtitle mono">{row.sku}</span>
              </td>
              <td>{comparisonValue(row.required_quantity)}</td>
              <td>{comparisonValue(row.observed_quantity)}</td>
              <td>{comparisonValue(row.difference)}</td>
              <td>
                <span
                  className={`comparison-state comparison-${row.status.toLowerCase().replaceAll("_", "-")}`}
                >
                  {label(row.status)}
                </span>
              </td>
              <td>
                {row.evidence_region_ids.length ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onSelectRegions(row.evidence_region_ids)}
                    aria-label={`Highlight evidence regions for ${row.sku}`}
                  >
                    View {row.evidence_region_ids.length} region
                    {row.evidence_region_ids.length === 1 ? "" : "s"}
                  </Button>
                ) : (
                  <span className="muted">No linked region</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function InspectionProgress({ inspection }: { inspection: Inspection }) {
  const events = inspection.execution_events ?? [];
  const metadata = inspection.provider_metadata;
  const providerStatus = (prefix: "MUSE" | "SAM") =>
    modelEventStatus(events, prefix, !!inspection.provider_error);
  const timing = (ms?: number) =>
    ms != null && Number.isFinite(ms)
      ? `${(ms / 1000).toFixed(2)} s`
      : "Not recorded";
  return (
    <div className="inspection-processing">
      <div className="processing-stage" role="status">
        <Activity size={16} aria-hidden="true" />
        <span>Current phase</span>
        <strong>
          {inspection.processing_stage
            ? label(inspection.processing_stage)
            : "Not recorded"}
        </strong>
      </div>
      <div className="model-status-grid">
        <div>
          <span>Muse Spark</span>
          <strong>{metadata?.muse_model ?? "muse-spark-1.3"}</strong>
          <p>
            {providerStatus("MUSE")} · {timing(metadata?.muse_latency_ms)}
          </p>
        </div>
        <div>
          <span>SAM segmentation</span>
          <strong>{metadata?.sam_model ?? "sam-3.1"}</strong>
          <p>
            {providerStatus("SAM")} · {timing(metadata?.sam_latency_ms)}
          </p>
        </div>
      </div>
      {metadata?.total_latency_ms != null && (
        <p className="processing-total">
          Backend processing time: {timing(metadata.total_latency_ms)}
        </p>
      )}
      {inspection.provider_error_details && (
        <div className="provider-error-details" role="status">
          <strong>{label(inspection.provider_error_details.category)}</strong>
          <span>
            {inspection.provider_error_details.http_status != null
              ? `HTTP ${inspection.provider_error_details.http_status} · `
              : ""}
            {inspection.provider_error_details.retryable
              ? "Provider failure can be retried explicitly."
              : "Check provider configuration and the reported failure before retrying."}
          </span>
        </div>
      )}
      <details
        className="execution-trace"
        open={inspection.status === "ANALYZING"}
      >
        <summary>
          Actual execution events <span>{events.length}</span>
        </summary>
        {events.length ? (
          <ol>
            {events.map((event) => (
              <li key={event.id}>
                <span className="execution-event-dot" />
                <div>
                  <strong>{label(event.event_type)}</strong>
                  <time dateTime={event.created_at}>
                    {formatTime(event.created_at)}
                  </time>
                  {Object.keys(event.details ?? {}).length > 0 && (
                    <details>
                      <summary>Recorded details</summary>
                      <pre>{JSON.stringify(event.details, null, 2)}</pre>
                    </details>
                  )}
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <p className="form-hint">
            No execution events are recorded. No model activity is simulated.
          </p>
        )}
      </details>
    </div>
  );
}
