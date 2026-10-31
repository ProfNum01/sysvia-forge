"""Bounded live Meta check on original synthetic before/after fixtures.

No database mutation, no credentials or raw model output printed.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from backend.app.services.provider import run_visual_models
from backend.app.services.reconciliation import reconcile
from proofsight.meta_api import MetaConfig


def main():
    config = MetaConfig.from_env()
    root = Path(__file__).resolve().parents[1]
    products = [
        {"id": "product-red", "sku": "PS-RED-01", "name": "Red Package",
         "color": "red", "description": "Red package with readable PS-RED-01 label",
         "reference_image_path": str(root / "data/references/product-red.png")},
        {"id": "product-blue", "sku": "PS-BLUE-02", "name": "Blue Package",
         "color": "blue", "description": "Blue package with readable PS-BLUE-02 label",
         "reference_image_path": str(root / "data/references/product-blue.png")},
    ]
    print(f"endpoint={config.base_url} muse={config.muse_model} sam={config.sam_model}", flush=True)
    with TemporaryDirectory() as directory:
        for stage in ("missing", "correct"):
            image = root / "data/fixtures" / f"task002-{stage}.png"
            result = run_visual_models(str(image), products, Path(directory) / f"{stage}.png")
            expected = [{"product_id": "product-red", "sku": "PS-RED-01", "name": "Red Package", "quantity": 2},
                        {"product_id": "product-blue", "sku": "PS-BLUE-02", "name": "Blue Package", "quantity": 1}]
            reconciliation = reconcile(expected, result["observations"], bool(result["regions"]),
                                       catalog=products, regions=result["regions"])
            print(f"{stage}: muse_ok={result['muse']['ok']} sam_ok={bool(result['sam'] and result['sam']['ok'])} "
                  f"sam_requests={(result['sam'] or {}).get('requests', 0)} "
                  f"observations={len(result['observations'])} regions={len(result['regions'])} "
                  f"reconciliation={reconciliation['reconciliation_status']}", flush=True)
            if not result["muse"]["ok"] or not result["sam"] or not result["sam"]["ok"]:
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
