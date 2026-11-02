export function investigationOutcome(decision: string | undefined, inspectionStatus: string) {
  if (decision === "HUMAN_REVIEW_REQUIRED") return {
    title: "مطلوب تدخل بشري",
    subtitle: "الأدلة غير كافية لحسم المطابقة. راجع الفحص قبل أي إجراء.",
  };
  if (decision === "CORRECTIVE_ACTION_REQUIRED") return {
    title: "مطلوب إجراء تصحيحي",
    subtitle: "تم اقتراح تصحيح؛ تنفيذه يتطلب موافقة المشرف ثم فحصًا جديدًا.",
  };
  if (decision === "EXISTING_ACTION_IN_PROGRESS") return {
    title: "إجراء تصحيحي قيد المتابعة",
    subtitle: "انتظر اكتمال الإجراء ثم افحص صورة جديدة لتأكيد النتيجة.",
  };
  if (decision === "NO_ACTION_REQUIRED" && inspectionStatus === "VERIFIED") return {
    title: "الفحص يؤيد الطلب",
    subtitle: "المطابقة مثبتة بالفحص المسجل. الشحن يتطلب انتقاله المعتمد منفصلًا.",
  };
  if (decision === "NO_ACTION_REQUIRED") return {
    title: "لا إجراء تصحيحي مقترح",
    subtitle: "الفحص لم يُعتمد كمطابق؛ راجع الأدلة وحالة الطلب.",
  };
  return { title: "نتيجة التحقيق تحتاج مراجعة", subtitle: "راجع القرار المسجل وتفاصيل الأدلة." };
}
