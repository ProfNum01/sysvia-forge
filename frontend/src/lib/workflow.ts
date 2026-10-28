export function buildInspectionUpload(image: File, orderId?: string): FormData {
  const body = new FormData();
  body.append("image", image);
  body.append("rights_confirmed", "true");
  if (orderId) body.append("order_id", orderId);
  return body;
}

export class UploadIdempotency {
  private current: {
    file: File;
    orderId: string;
    parentId: string | null;
    key: string;
  } | null = null;
  private makeKey: () => string;
  constructor(makeKey: () => string = () => crypto.randomUUID()) {
    this.makeKey = makeKey;
  }
  reset() {
    this.current = null;
  }
  keyFor(file: File, orderId: string, parentId: string | null): string {
    if (
      !this.current ||
      this.current.file !== file ||
      this.current.orderId !== orderId ||
      this.current.parentId !== parentId
    ) {
      this.current = { file, orderId, parentId, key: this.makeKey() };
    }
    return this.current.key;
  }
}

export function inspectionHref(order: {
  id: string;
  latest_inspection_id?: string | null;
}): string {
  return order.latest_inspection_id
    ? `/inspection?id=${encodeURIComponent(order.latest_inspection_id)}`
    : `/inspection?order=${encodeURIComponent(order.id)}`;
}

export function canAnalyzeInspection(
  inspection: { id: string; status: string },
  order:
    | { latest_inspection_id?: string | null; preparation_status: string }
    | undefined,
): boolean {
  return (
    !!order &&
    order.latest_inspection_id === inspection.id &&
    order.preparation_status !== "PREPARING" &&
    ["UPLOADED", "PROVIDER_ERROR"].includes(inspection.status)
  );
}

export function canReinspectInspection(
  inspection: { id: string; status: string },
  latestId?: string | null,
): boolean {
  return (
    latestId === inspection.id &&
    !["UPLOADED", "ANALYZING"].includes(inspection.status)
  );
}
