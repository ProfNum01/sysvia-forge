from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from proofsight.meta_api import (  # noqa: E402
    MetaConfig,
    MetaConfigurationError,
    MuseSparkService,
    SamSegmentationService,
    classify_api_error,
    create_muse_client,
    create_sam_client,
)


async def _run_sam(config: MetaConfig, image: Path, prompt: str):
    client = create_sam_client(config)
    try:
        return await SamSegmentationService(client, config.sam_model).segment(
            image, prompt, ROOT / "artifacts" / "sam-annotated.png")
    finally:
        await client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run bounded live Meta API connectivity checks.")
    parser.add_argument("--image", type=Path, help="Rights-cleared local image for one SAM request")
    parser.add_argument("--prompt", default="a cardboard box", help="Concrete object phrase for SAM")
    args = parser.parse_args()
    report: dict = {"configuration": {}, "muse_spark": {}, "sam": {}, "negative_path_categories": [
        "authentication", "permission_or_billing", "model_or_endpoint", "rate_limit", "timeout", "connection", "service_error"
    ]}
    try:
        config = MetaConfig.from_env()
        report["configuration"] = {**config.public_status(), "api_key_present": True}
    except MetaConfigurationError as exc:
        report["configuration"] = {"configured": False, "error": str(exc), "base_url": "https://api.meta.ai/v1",
                                    "muse_model": "muse-spark-1.3", "sam_model": "sam-3.1"}
        report["muse_spark"] = {"status": "BLOCKED", "reason": "Meta API configuration is unavailable"}
        report["sam"] = {"status": "BLOCKED", "reason": "Meta API configuration is unavailable"}
        print(json.dumps(report, indent=2))
        return 2

    muse_ok = False
    try:
        client = create_muse_client(config)
        try:
            muse = MuseSparkService(client, config.muse_model).ping()
        finally:
            client.close()
        muse_ok = muse.ok
        muse_report = muse.as_dict()
        muse_report.pop("response", None)
        report["muse_spark"] = {"status": "PASS" if muse_ok else "FAIL", **muse_report}
    except Exception as exc:
        report["muse_spark"] = {"status": "FAIL", "ok": False, "error": classify_api_error(exc)}
    if args.image is None:
        report["sam"] = {"status": "BLOCKED", "reason": "Real test image required; provide --image with rights-cleared media"}
    elif not args.image.is_file():
        report["sam"] = {"status": "BLOCKED", "reason": "Specified test image does not exist"}
    else:
        try:
            result = asyncio.run(_run_sam(config, args.image, args.prompt))
            report["sam"] = {"status": "PASS" if result.ok else "FAIL", **result.as_dict()}
        except (OSError, ValueError):
            report["sam"] = {"status": "BLOCKED", "reason": "A supported readable image and concrete prompt are required"}
        except Exception as exc:
            report["sam"] = {"status": "FAIL", "ok": False, "error": classify_api_error(exc)}
    print(json.dumps(report, indent=2))
    if not muse_ok or report["sam"]["status"] == "FAIL":
        return 1
    return 2 if report["sam"]["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
