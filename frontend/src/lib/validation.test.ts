import { describe, expect, it } from "vitest";
import { validateImage } from "./validation";
describe("rights-cleared inspection image policy", () => {
  it("requires explicit rights acknowledgement", () =>
    expect(validateImage({ type: "image/png", size: 100 }, false)).toMatch(
      /rights/,
    ));
  it("rejects unsupported media", () =>
    expect(validateImage({ type: "image/svg+xml", size: 100 }, true)).toMatch(
      /PNG/,
    ));
  it("rejects oversized images", () =>
    expect(
      validateImage({ type: "image/jpeg", size: 15 * 1024 * 1024 + 1 }, true),
    ).toMatch(/15/));
  it("requires an image", () =>
    expect(validateImage(null, true)).toMatch(/Choose/));
  it("allows an acknowledged supported file at the limit", () =>
    expect(
      validateImage({ type: "image/webp", size: 15 * 1024 * 1024 }, true),
    ).toBeNull());
});
