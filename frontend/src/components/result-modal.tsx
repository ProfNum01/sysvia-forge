import React, { createContext, useContext, useState, useCallback } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  CircleAlert,
  Sparkles,
  X,
  ShieldAlert,
} from "lucide-react";
import { Button } from "./ui/button";
import { label } from "../lib/api";
import type { Inspection } from "../types";

export type ResultModalPayload = {
  isOpen: boolean;
  type: "INSPECTION" | "INVESTIGATION" | "ACTION" | "SHIPPING";
  status: string;
  title: string;
  subtitle?: string;
  orderReference?: string;
  inspectionId?: string;
  orderId?: string;
  discrepancies?: {
    product_id?: string;
    type: string;
    description: string;
    required_quantity?: number;
    observed_quantity?: number;
  }[];
  comparison?: {
    product_id: string;
    name: string;
    required_quantity: number;
    observed_quantity?: number | null;
    status: string;
  }[];
  diagnosis?: string;
  actions?: {
    label: string;
    onClick: () => void;
    variant?:
      | "default"
      | "primary"
      | "outline"
      | "ghost"
      | "destructive"
      | "success"
      | "warning"
      | "agent"
      | "inspect"
      | "subtle";
  }[];
};

type ResultModalContextType = {
  activeResult: ResultModalPayload | null;
  showResult: (payload: Omit<ResultModalPayload, "isOpen">) => void;
  showInspectionResult: (
    inspection: Inspection,
    orderReference?: string,
    onInvestigate?: () => void,
  ) => void;
  closeResult: () => void;
};

const ResultModalContext = createContext<ResultModalContextType>({
  activeResult: null,
  showResult: () => {},
  showInspectionResult: () => {},
  closeResult: () => {},
});

export function useResultModal() {
  return useContext(ResultModalContext);
}

export function buildInspectionDiagnosis(inspection: Inspection): {
  title: string;
  subtitle: string;
  diagnosis: string;
  status: string;
} {
  const status = inspection.status;
  const discrepancies = inspection.discrepancies || [];

  if (status === "VERIFIED") {
    return {
      title: "فحص مطابق ومعتمد · Verified Reality",
      subtitle: `تم مطابقة كافة متطلبات الطلب مع الأدلة البصرية (Photo ID: ${inspection.photo_id.slice(0, 10)})`,
      diagnosis:
        "تطابق تام ومثبت: تم التحقق من جميع المنتجات والكميات المطلوبة ومطابقتها حتمياً مع مانيفست الطلب بدون أي عجز أو شك.",
      status,
    };
  }

  if (status === "NEEDS_REVIEW" || status === "HELD") {
    const shortfalls = discrepancies.filter((d) => d.type === "SHORTFALL");
    const notObserved = discrepancies.filter((d) => d.type === "NOT_OBSERVED");
    const uncertain = discrepancies.filter(
      (d) => d.type === "UNCERTAIN" || d.type === "UNIDENTIFIED",
    );
    const excess = discrepancies.filter(
      (d) => d.type === "EXCESS" || d.type === "EXTRA_PRODUCT",
    );

    const reasons: string[] = [];
    if (shortfalls.length > 0) {
      reasons.push(
        `عجز في الكمية (${shortfalls.length} منتج): الكمية المرصودة بالصورة أقل من مانيفست الطلب المطلوب.`,
      );
    }
    if (notObserved.length > 0) {
      reasons.push(
        `منتجات لم تُرصد (${notObserved.length} منتج): عدم الرصد بالصورة لا يثبت الغياب الحتمي بموجب سياسة التدقيق الصارمة.`,
      );
    }
    if (uncertain.length > 0) {
      reasons.push(
        `عناصر غير مؤكدة الهوية (${uncertain.length}): تعذر على الرؤية قراءة ملصق SKU أو ربط قناع SAM بدقة.`,
      );
    }
    if (excess.length > 0) {
      reasons.push(
        `زيادة أو منتجات إضافية (${excess.length}): وُجدت عناصر غير مسجلة في مانيفست هذا الطلب.`,
      );
    }

    const diagnosisText =
      reasons.length > 0
        ? reasons.join("\n• ")
        : "تم وضع الفحص قيد المراجعة لوجود تباين بين المانيفست الرقمي والأدلة المرئية.";

    return {
      title:
        status === "HELD"
          ? "الفحص معلق · Inspection Held"
          : "الفحص يحتاج مراجعة · Needs Review",
      subtitle: `رُصد ${discrepancies.length} تباين(ات) بين مانيفست الطلب والصورة الملتقطة (Photo ID: ${inspection.photo_id.slice(0, 10)})`,
      diagnosis: `أسباب المراجعة والتعليق البصري:\n• ${diagnosisText}`,
      status,
    };
  }

  return {
    title: `نتيجة الفحص · ${label(status)}`,
    subtitle: `حالة المعالجة الحالية: ${label(inspection.reconciliation_status ?? status)}`,
    diagnosis:
      inspection.provider_error ??
      "جاري التدقيق أو بانتظار استكمال الإجراءات التصحيحية المعتمدة.",
    status,
  };
}

export function ResultModalProvider({ children }: { children: React.ReactNode }) {
  const [activeResult, setActiveResult] = useState<ResultModalPayload | null>(null);

  const showResult = useCallback((payload: Omit<ResultModalPayload, "isOpen">) => {
    setActiveResult({ ...payload, isOpen: true });
  }, []);

  const showInspectionResult = useCallback(
    (
      inspection: Inspection,
      orderReference?: string,
      onInvestigate?: () => void,
    ) => {
      const diag = buildInspectionDiagnosis(inspection);
      const isNeedsReview =
        inspection.status === "NEEDS_REVIEW" || inspection.status === "HELD";

      const actions: ResultModalPayload["actions"] = [];
      if (isNeedsReview && onInvestigate) {
        actions.push({
          label: "بدء التحقيق بالذكاء الاصطناعي (Start AI Investigation)",
          onClick: onInvestigate,
          variant: "agent",
        });
      }

      showResult({
        type: "INSPECTION",
        status: diag.status,
        title: diag.title,
        subtitle: diag.subtitle,
        orderReference,
        inspectionId: inspection.id,
        orderId: inspection.order_id,
        discrepancies: inspection.discrepancies,
        comparison: inspection.comparison?.map((c) => ({
          product_id: c.product_id,
          name: c.name,
          required_quantity: c.required_quantity,
          observed_quantity: c.observed_quantity,
          status: c.status,
        })),
        diagnosis: diag.diagnosis,
        actions,
      });
    },
    [showResult],
  );

  const closeResult = useCallback(() => {
    setActiveResult(null);
  }, []);

  return (
    <ResultModalContext.Provider
      value={{ activeResult, showResult, showInspectionResult, closeResult }}
    >
      {children}
      {activeResult && activeResult.isOpen && (
        <ResultModalDialog payload={activeResult} onClose={closeResult} />
      )}
    </ResultModalContext.Provider>
  );
}

function ResultModalDialog({
  payload,
  onClose,
}: {
  payload: ResultModalPayload;
  onClose: () => void;
}) {
  const isVerified = payload.status === "VERIFIED";
  const isNeedsReview =
    payload.status === "NEEDS_REVIEW" || payload.status === "HELD";
  const isMismatch =
    payload.status === "MISMATCH_DETECTED" || payload.status === "FAILED";

  const statusTone = isVerified
    ? "verified"
    : isMismatch
      ? "danger"
      : isNeedsReview
        ? "warning"
        : "neutral";

  return (
    <div
      className="result-modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="result-modal-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className={`result-modal modal-tone-${statusTone}`}>
        <div className="result-modal-header">
          <div className="modal-title-wrap">
            <span className={`modal-status-pill pill-${statusTone}`}>
              {isVerified ? (
                <CheckCircle2 size={16} aria-hidden="true" />
              ) : isNeedsReview ? (
                <AlertTriangle size={16} aria-hidden="true" />
              ) : (
                <ShieldAlert size={16} aria-hidden="true" />
              )}
              {label(payload.status)}
            </span>
            <h2 id="result-modal-title">{payload.title}</h2>
            {payload.subtitle && <p className="modal-subtitle">{payload.subtitle}</p>}
          </div>
          <button
            type="button"
            className="modal-close-btn"
            aria-label="Close result dialog"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </div>

        <div className="result-modal-body">
          {/* Key diagnosis explanation box */}
          {payload.diagnosis && (
            <div className={`modal-diagnosis-box box-${statusTone}`}>
              <div className="diagnosis-box-title">
                {isVerified ? (
                  <CheckCircle2 size={15} />
                ) : (
                  <CircleAlert size={15} />
                )}
                <strong>تشخيص نتيجة الفحص (Outcome Diagnosis)</strong>
              </div>
              <pre className="diagnosis-text">{payload.diagnosis}</pre>
            </div>
          )}

          {/* Comparison / Discrepancy Highlight Table */}
          {payload.comparison && payload.comparison.length > 0 && (
            <div className="modal-table-section">
              <div className="modal-section-title">
                <strong>تفاصيل المطابقة البصرية بين المانيفست والواقع</strong>
                <span className="section-note">
                  العناصر المعلم عليها بالأصفر أو الأحمر تتطلب معالجة
                </span>
              </div>
              <div className="table-wrap modal-table-wrap">
                <table className="modal-comparison-table">
                  <thead>
                    <tr>
                      <th>المنتج (Product)</th>
                      <th>المطلوب (Req)</th>
                      <th>المرصود بالصورة (Obs)</th>
                      <th>حالة المطابقة (Status)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {payload.comparison.map((row) => {
                      const isRowDiscrepancy = row.status !== "MATCHED";
                      return (
                        <tr
                          key={row.product_id}
                          className={isRowDiscrepancy ? "row-highlight-error" : "row-highlight-success"}
                        >
                          <td>
                            <strong>{row.name}</strong>
                          </td>
                          <td>{row.required_quantity}</td>
                          <td>
                            <strong>{row.observed_quantity ?? "غير مرصود"}</strong>
                          </td>
                          <td>
                            <span
                              className={`status status-${row.status.toLowerCase().replaceAll("_", "-")}`}
                            >
                              <span />
                              {label(row.status)}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Inspection and Order context metadata */}
          <div className="modal-context-strip">
            {payload.orderReference && (
              <span>
                الطلب: <strong>{payload.orderReference}</strong>
              </span>
            )}
            {payload.inspectionId && (
              <span>
                معرف الفحص: <code>{payload.inspectionId.slice(0, 12)}</code>
              </span>
            )}
            <span>
              نظام الفحص: <strong>Meta Muse Spark 1.3 + SAM 3.1</strong>
            </span>
          </div>
        </div>

        <div className="result-modal-footer">
          {payload.actions &&
            payload.actions.map((act, idx) => (
              <Button
                key={idx}
                variant={act.variant ?? "default"}
                onClick={() => {
                  act.onClick();
                  onClose();
                }}
              >
                <Sparkles size={14} aria-hidden="true" />
                {act.label}
              </Button>
            ))}
          <Button variant="outline" onClick={onClose}>
            إغلاق (Dismiss)
          </Button>
        </div>
      </div>
    </div>
  );
}
