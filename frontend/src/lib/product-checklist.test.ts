import { describe, expect, it } from "vitest";
import { checklistState } from "./product-checklist";

describe("product evidence checklist", () => {
  it("checks only server matched quantities", () => {
    expect(checklistState({ required_quantity: 2, observed_quantity: 2, status: "MATCHED" })).toEqual({ checked: true, text: "2 / 2 confirmed" });
  });

  it("leaves uncertain and unanalysed products unresolved", () => {
    expect(checklistState({ required_quantity: 1, observed_quantity: null, status: "UNCERTAIN" })).toEqual({ checked: false, text: "Not established · needs review" });
    expect(checklistState({ required_quantity: 1, observed_quantity: 1, status: "UNCERTAIN" }).checked).toBe(false);
  });
});
