export type PixelBox = {
  left: number;
  top: number;
  right: number;
  bottom: number;
};

export function sourceBox(box: PixelBox) {
  if (
    ![box.left, box.top, box.right, box.bottom].every(Number.isFinite) ||
    box.left < 0 ||
    box.top < 0 ||
    box.right <= box.left ||
    box.bottom <= box.top
  )
    return null;
  return {
    x: box.left,
    y: box.top,
    width: box.right - box.left,
    height: box.bottom - box.top,
  };
}

export function maskTransform(mask: {
  width: number;
  height: number;
  bounds: PixelBox;
}): string | null {
  const bounds = sourceBox(mask.bounds);
  if (
    !bounds ||
    !Number.isFinite(mask.width) ||
    !Number.isFinite(mask.height) ||
    mask.width <= 0 ||
    mask.height <= 0
  )
    return null;
  return `translate(${bounds.x} ${bounds.y}) scale(${bounds.width / mask.width} ${bounds.height / mask.height})`;
}

export function regionLabel(
  region: { product_id?: string | null; candidate_product_id?: string | null },
  products: { id: string; sku: string }[],
): string {
  if (!region.product_id) return "UNIDENTIFIED";
  return (
    products.find((product) => product.id === region.product_id)?.sku ??
    "UNIDENTIFIED"
  );
}

export function comparisonValue(value: number | null | undefined): string {
  return value == null || !Number.isFinite(value)
    ? "Not established"
    : String(value);
}

export function modelEventStatus(
  events: { event_type: string }[],
  prefix: "MUSE" | "SAM",
  hasError: boolean,
): string {
  const stage = prefix === "MUSE" ? "ANALYSIS" : "SEGMENTATION";
  const relevant = events.filter(
    (event) =>
      event.event_type === `${prefix}_${stage}_STARTED` ||
      event.event_type === `${prefix}_${stage}_COMPLETED` ||
      (event.event_type.startsWith(`${prefix}_`) &&
        event.event_type.endsWith("_FAILED")),
  );
  const latest = relevant.at(-1)?.event_type;
  if (!latest) return "Not recorded";
  if (latest.endsWith("_COMPLETED")) return "Completed";
  if (latest.endsWith("_FAILED")) return "Failed";
  return hasError ? "Incomplete" : "Started";
}
