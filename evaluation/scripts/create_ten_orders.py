"""Generate ten deterministic synthetic whole-order scenes and manifests."""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evaluation/datasets/ten-orders"
SKUS = ("BLUE-BOX", "RED-CAN", "YELLOW-POUCH", "GREEN-CUBE")
COLORS = {"BLUE-BOX": "#176ac8", "RED-CAN": "#c32b32", "YELLOW-POUCH": "#f2cf00", "GREEN-CUBE": "#16885b"}
SCENARIOS = [
    ("single-blue", {"BLUE-BOX": 1}, {"BLUE-BOX": 1}),
    ("blue-red-pair", {"BLUE-BOX": 1, "RED-CAN": 1}, {"BLUE-BOX": 1, "RED-CAN": 1}),
    ("two-cans-one-pouch", {"RED-CAN": 2, "YELLOW-POUCH": 1}, {"RED-CAN": 2, "YELLOW-POUCH": 1}),
    ("four-sku-assortment", {s: 1 for s in SKUS}, {s: 1 for s in SKUS}),
    ("two-blue-two-green", {"BLUE-BOX": 2, "GREEN-CUBE": 2}, {"BLUE-BOX": 2, "GREEN-CUBE": 2}),
    ("mixed-five", {"BLUE-BOX": 2, "RED-CAN": 1, "YELLOW-POUCH": 1, "GREEN-CUBE": 1}, {"BLUE-BOX": 2, "RED-CAN": 1, "YELLOW-POUCH": 1, "GREEN-CUBE": 1}),
    ("missing-red-can", {"BLUE-BOX": 1, "RED-CAN": 1}, {"BLUE-BOX": 1}),
    ("extra-green-cube", {"YELLOW-POUCH": 1}, {"YELLOW-POUCH": 1, "GREEN-CUBE": 1}),
    ("wrong-product-substitution", {"BLUE-BOX": 1, "RED-CAN": 1}, {"BLUE-BOX": 1, "YELLOW-POUCH": 1}),
    ("wrong-blue-quantity", {"BLUE-BOX": 2, "GREEN-CUBE": 1}, {"BLUE-BOX": 1, "GREEN-CUBE": 1}),
]


def font(size):
    path = Path("C:/Windows/Fonts/arialbd.ttf")
    return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()


def draw_product(draw, sku, x, y):
    color = COLORS[sku]
    if sku == "RED-CAN":
        draw.rounded_rectangle((x + 30, y + 10, x + 190, y + 178), 35, fill=color, outline="#333333", width=3)
        draw.ellipse((x + 30, y, x + 190, y + 38), fill="#c0c3c9", outline="#444444", width=3)
    elif sku == "YELLOW-POUCH":
        draw.polygon([(x + 25, y + 10), (x + 195, y + 10), (x + 205, y + 180), (x + 15, y + 180)], fill=color)
        draw.line((x + 25, y + 10, x + 195, y + 10), fill="#806c00", width=4)
    else:
        draw.rectangle((x + 10, y + 18, x + 205, y + 180), fill=color, outline="#25313d", width=3)
        draw.polygon([(x + 10, y + 18), (x + 45, y), (x + 205, y), (x + 205, y + 18)], fill="#ffffff55")
    draw.rectangle((x + 15, y + 92, x + 205, y + 144), fill="white", outline="black", width=3)
    draw.text((x + 110, y + 118), sku, fill="black", font=font(19), anchor="mm")


def main():
    (OUT / "orders").mkdir(parents=True, exist_ok=True)
    (OUT / "images").mkdir(parents=True, exist_ok=True)
    cases = []
    for number, (scenario, expected, actual) in enumerate(SCENARIOS, 1):
        order_id = f"TEN-ORDER-{number:02d}"
        evidence = f"evaluation/datasets/ten-orders/images/{order_id}.png"
        image = Image.new("RGB", (1200, 900), "#e9edf1")
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((55, 75, 1145, 825), 28, fill="#dad3c8", outline="#77726c", width=5)
        draw.text((600, 35), f"SYNTHETIC PACKING SCENE  {order_id}", fill="#263238", font=font(30), anchor="mm")
        items = [sku for sku in SKUS for _ in range(actual.get(sku, 0))]
        for i, sku in enumerate(items):
            x = 105 + (i % 4) * 250
            y = 185 + (i // 4) * 280
            draw_product(draw, sku, x, y)
        image.save(ROOT / evidence)
        (OUT / "orders" / f"{order_id}.json").write_text(json.dumps({"reference": order_id, "provenance": "SYNTHETIC", "items": expected, "image": evidence}, indent=2) + "\n", encoding="utf-8")
        if expected == actual:
            discrepancies = []
        elif any(actual.get(s, 0) < q for s, q in expected.items()) and any(actual.get(s, 0) > expected.get(s, 0) for s in actual):
            discrepancies = ["SUBSTITUTION_OR_REVIEW"]
        elif any(actual.get(s, 0) < q for s, q in expected.items()):
            discrepancies = ["SHORTFALL_OR_REVIEW"]
        else:
            discrepancies = ["EXTRA_PRODUCT_OR_REVIEW"]
        cases.append({"scenario_id": scenario, "order_id": order_id, "expected_quantities": expected,
                      "ground_truth_quantities": actual, "evidence": evidence, "provenance": "SYNTHETIC",
                      "expected_discrepancy": discrepancies,
                      "expected_agent_behavior": "NO_INVESTIGATION" if not discrepancies else "INVESTIGATE_WITH_READ_TOOLS_AND_PROPOSE_REVIEW",
                      "expected_verification_policy": "VERIFY_ONLY_WITH_SUFFICIENT_EVIDENCE" if not discrepancies else "BLOCK_UNTIL_NEW_EVIDENCE",
                      "human_review_required": bool(discrepancies)})
    manifest = {"dataset_id": "ten-synthetic-whole-orders-v1", "generator": "ProofSight deterministic Pillow drawings",
                "provenance": "SYNTHETIC", "catalog": {sku: sku for sku in SKUS}, "cases": cases}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Created {len(cases)} synthetic orders and whole-order images in {OUT}")


if __name__ == "__main__":
    main()
