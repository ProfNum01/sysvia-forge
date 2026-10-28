from __future__ import annotations

import os
import asyncio
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
from openai import OpenAI
from PIL import Image

from proofsight.meta_api import MetaConfig, MetaConfigurationError, MuseSparkService, SamSegmentationService, classify_api_error


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root_patch = patch("proofsight.meta_api.ROOT", self.root, create=True)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def test_loads_project_dotenv_without_replacing_process_environment(self):
        (self.root / ".env").write_text("MODEL_API_KEY=local-test-secret\n", encoding="utf-8")
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(MetaConfig.from_env().api_key, "local-test-secret")
        with patch.dict(os.environ, {"MODEL_API_KEY": "process-test-secret"}, clear=True):
            self.assertEqual(MetaConfig.from_env().api_key, "process-test-secret")

    def test_explicit_env_file_is_existing_file_and_takes_place_of_default(self):
        (self.root / ".env").write_text("MODEL_API_KEY=default-test-secret\n", encoding="utf-8")
        (self.root / "chosen.env").write_text("MODEL_API_KEY=explicit-test-secret\n", encoding="utf-8")
        with patch.dict(os.environ, {"PROOFSIGHT_ENV_FILE": "chosen.env"}, clear=True):
            self.assertEqual(MetaConfig.from_env().api_key, "explicit-test-secret")
        for filename in ("missing.env", "."):
            with self.subTest(filename=filename), patch.dict(os.environ, {"PROOFSIGHT_ENV_FILE": filename}, clear=True):
                with self.assertRaises(MetaConfigurationError):
                    MetaConfig.from_env()

    def test_key_is_excluded_from_repr_and_public_status(self):
        config = MetaConfig(api_key="secret-for-test")
        self.assertNotIn("secret-for-test", repr(config))
        self.assertNotIn("secret-for-test", json.dumps(config.public_status()))

    def test_loads_expected_environment_variables(self):
        with patch.dict(os.environ, {"MODEL_API_KEY": "test-secret"}, clear=True):
            config = MetaConfig.from_env()
        self.assertEqual(config.api_key, "test-secret")
        self.assertEqual(config.base_url, "https://api.meta.ai/v1")
        self.assertEqual(config.muse_model, "muse-spark-1.3")
        self.assertEqual(config.sam_model, "sam-3.1")

    def test_missing_key_fails_without_echoing_secret(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(MetaConfigurationError) as caught:
                MetaConfig.from_env()
        self.assertNotIn("test-secret", str(caught.exception))

    def test_refuses_unapproved_base_url(self):
        with patch.dict(os.environ, {"MODEL_API_KEY": "test", "META_API_BASE_URL": "https://evil.invalid/v1"}, clear=True):
            with self.assertRaises(MetaConfigurationError):
                MetaConfig.from_env()


class MuseServiceTests(unittest.TestCase):
    def test_ping_reports_model_latency_usage_and_response(self):
        client = Mock()
        client.chat.completions.create.return_value = Mock(
            model="muse-spark-1.3", choices=[Mock(message=Mock(content="ready"))],
            usage=Mock(prompt_tokens=5, completion_tokens=1, total_tokens=6),
        )
        service = MuseSparkService(client, "muse-spark-1.3")
        with patch("proofsight.meta_api.time.perf_counter", side_effect=[1.0, 1.125]):
            result = service.ping()
        self.assertTrue(result.ok)
        self.assertEqual(result.model, "muse-spark-1.3")
        self.assertEqual(result.response, "ready")
        self.assertEqual(result.latency_ms, 125)
        self.assertEqual(result.usage["total_tokens"], 6)
        client.chat.completions.create.assert_called_once()

    def test_model_mismatch_is_not_success(self):
        client = Mock()
        client.chat.completions.create.return_value = Mock(model="different", choices=[Mock(message=Mock(content="ready"))], usage=None)
        result = MuseSparkService(client, "muse-spark-1.3").ping()
        self.assertFalse(result.ok)

    def test_api_error_is_returned_without_crashing_or_leaking_body(self):
        client = Mock()
        error = Exception("sensitive provider response")
        error.status_code = 429
        client.chat.completions.create.side_effect = error
        result = MuseSparkService(client, "muse-spark-1.3").ping()
        self.assertFalse(result.ok)
        self.assertEqual(result.http_status, 429)
        self.assertEqual(result.error["category"], "rate_limit")
        self.assertNotIn("sensitive", str(result.as_dict()))


class ErrorClassificationTests(unittest.TestCase):
    def test_classifies_common_sdk_status_errors_without_message_content(self):
        for status, expected in [(401, "authentication"), (403, "permission_or_billing"), (404, "model_or_endpoint"), (429, "rate_limit"), (400, "request_error"), (503, "service_error")]:
            error = Exception("sensitive response body")
            error.status_code = status
            result = classify_api_error(error)
            self.assertEqual(result["category"], expected)
            self.assertNotIn("sensitive", str(result))

    def test_classifies_timeout_and_connection(self):
        class ConnectError(Exception):
            pass
        self.assertEqual(classify_api_error(TimeoutError("timeout"))["category"], "timeout")
        self.assertEqual(classify_api_error(ConnectError("offline"))["category"], "connection")


class VisualInspectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.image = Path(self.temp.name) / "test.png"
        Image.new("RGB", (10, 10), "white").save(self.image)
        self.catalog = [{"id": "p1", "sku": "SKU-001", "name": "Test box"}]
        self.observation = {"product_id": "p1", "quantity": 1, "label_text": "SKU-001",
                            "evidence": "One front-facing readable SKU label", "identity_certain": True,
                            "count_certain": True}
        self.requests = []

    def service(self, content, model="muse-spark-1.3", finish_reason="stop", status=200):
        def respond(request):
            self.requests.append(json.loads(request.content))
            if status != 200:
                return httpx.Response(status, json={"error": {"message": "sensitive-provider-body"}})
            return httpx.Response(200, json={"id": "test-completion", "object": "chat.completion", "created": 1,
                "model": model, "choices": [{"index": 0, "finish_reason": finish_reason,
                "message": {"role": "assistant", "content": content}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}})
        client = OpenAI(api_key="test-only", base_url="https://api.meta.ai/v1", max_retries=0,
                        http_client=httpx.Client(transport=httpx.MockTransport(respond)))
        self.addCleanup(client.close)
        return MuseSparkService(client)

    def test_inspects_local_image_with_documented_sdk_contract(self):
        service = self.service(json.dumps({"observations": [self.observation]}))
        result = service.inspect_image(self.image, self.catalog)
        self.assertTrue(result["ok"])
        self.assertEqual(result["observations"], [{**self.observation, "source_box": None, "evidence_region_ids": []}])
        self.assertEqual(result["usage"]["total_tokens"], 30)
        self.assertEqual(result["http_status"], 200)
        request = self.requests[0]
        self.assertEqual(request["model"], "muse-spark-1.3")
        content = request["messages"][-1]["content"]
        self.assertEqual(content[-1]["type"], "image_url")
        self.assertTrue(content[-1]["image_url"]["url"].startswith("data:image/png;base64,"))
        self.assertEqual(request["response_format"]["type"], "json_schema")
        self.assertFalse(request["response_format"]["json_schema"]["schema"]["additionalProperties"])
        self.assertNotIn("tools", request)

    def test_uncertain_identity_and_quantity_remain_null(self):
        observation = {**self.observation, "product_id": None, "quantity": None, "label_text": "unreadable",
                       "identity_certain": False, "count_certain": False}
        result = self.service(json.dumps({"observations": [observation]})).inspect_image(self.image, self.catalog)
        self.assertTrue(result["ok"])
        self.assertIsNone(result["observations"][0]["quantity"])

    def test_empty_observations_do_not_claim_absence(self):
        result = self.service('{"observations": []}').inspect_image(self.image, self.catalog)
        self.assertTrue(result["ok"])
        self.assertEqual(result["observations"], [])
        self.assertNotIn("absent", result)

    def test_rejects_malformed_coerced_extra_or_inconsistent_observations(self):
        variants = ["sensitive model prose", '{"observations": "invalid"}',
                    json.dumps({"observations": [{**self.observation, "quantity": "1"}]}),
                    json.dumps({"observations": [{**self.observation, "confidence": 0.99}]}),
                    json.dumps({"observations": [{**self.observation, "quantity": -1}]}),
                    json.dumps({"observations": [{**self.observation, "quantity": 0}]}),
                    json.dumps({"observations": [{**self.observation, "count_certain": False}]}),
                    json.dumps({"observations": [{**self.observation, "product_id": "invented"}]})]
        for content in variants:
            with self.subTest(content=content):
                result = self.service(content).inspect_image(self.image, self.catalog)
                self.assertFalse(result["ok"])
                self.assertEqual(result["observations"], [])
                self.assertEqual(result["error"]["category"], "invalid_response")
                self.assertNotIn("sensitive model prose", str(result))

    def test_mismatched_model_or_truncated_response_is_not_success(self):
        for model, reason in [("other", "stop"), ("muse-spark-1.3", "length")]:
            result = self.service('{"observations": []}', model, reason).inspect_image(self.image, self.catalog)
            self.assertFalse(result["ok"])

    def test_provider_error_is_sanitized(self):
        result = self.service("", status=429).inspect_image(self.image, self.catalog)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["category"], "rate_limit")
        self.assertNotIn("sensitive-provider-body", str(result))

    def test_invalid_local_image_is_blocked_without_request(self):
        result = self.service("").inspect_image(self.image.parent / "missing.png", self.catalog)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["category"], "invalid_image")
        self.assertEqual(self.requests, [])

    def test_optional_reference_images_are_distinct_from_single_countable_scene(self):
        reference = self.image.parent / "reference.png"
        Image.new("RGB", (4, 4), "blue").save(reference)
        self.catalog[0]["reference_image_path"] = str(reference)
        self.catalog.append({"id": "p2", "sku": "SKU-002", "name": "Other", "reference_image_path": "missing.png"})
        result = self.service('{"observations": []}').inspect_image(self.image, self.catalog)
        self.assertTrue(result["ok"])
        content = self.requests[0]["messages"][-1]["content"]
        images = [entry for entry in content if entry["type"] == "image_url"]
        self.assertEqual(len(images), 2)
        labels = [entry["text"] for entry in content if entry["type"] == "text"]
        self.assertTrue(any("REFERENCE" in label and "p1" in label for label in labels))
        self.assertTrue(any("ACTUAL SCENE" in label and "10" in label for label in labels))
        self.assertNotEqual(images[0]["image_url"]["url"], images[-1]["image_url"]["url"])

    def test_scene_source_box_is_typed_and_bounded(self):
        box = {"left": 1, "top": 2, "right": 8, "bottom": 9}
        observation = {**self.observation, "source_box": box}
        result = self.service(json.dumps({"observations": [observation]})).inspect_image(self.image, self.catalog)
        self.assertTrue(result["ok"])
        self.assertEqual(result["observations"][0]["source_box"], box)
        for invalid in [{**box, "left": -1}, {**box, "right": 11}, {**box, "left": 9}, {**box, "left": "1"}]:
            result = self.service(json.dumps({"observations": [{**observation, "source_box": invalid}]})).inspect_image(self.image, self.catalog)
            self.assertFalse(result["ok"])
            self.assertEqual(result["error"]["category"], "invalid_response")


class EventStream:
    """In-memory SDK stream boundary; the actual SAM parser stays real."""
    def __init__(self, text):
        lane = {"item_id": "item-1", "output_index": 0, "content_index": 0}
        self.events = [{"type": "response.output_text.delta", **lane, "delta": text},
                       {"type": "response.content_part.done", **lane, "part": {"type": "output_text", "text": text}},
                       {"type": "response.completed", "response": {"model": "sam-3.1", "status": "completed"}}]

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def __aiter__(self):
        return self.iterate()

    async def iterate(self):
        for event in self.events:
            yield event


class SamServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.image = Path(self.temp.name) / "source.png"
        Image.new("RGB", (10, 10), "white").save(self.image)

    def service(self, text):
        self.client = SimpleNamespace(responses=SimpleNamespace(stream=Mock(return_value=EventStream(text))))
        return SamSegmentationService(self.client)

    async def test_stream_parser_decodes_geometry_and_serializes_box_local_rle(self):
        text = "<0f>0<|box;x1=2;y1=3;x2=6;y2=7;w=10;h=10|><|mask;x=0;y=0;data=5,5,!!!!!(QO(0lu8?|>\n"
        result = await self.service(text).segment(self.image, "a box", self.image.parent / "annotated.png")
        self.assertTrue(result.ok)
        self.assertEqual(result.boxes[0]["left"], 2)
        self.assertEqual(result.boxes[0]["right"], 7)
        self.assertEqual(result.masks[0]["rle"]["size"], [5, 5])
        self.assertTrue(result.masks[0]["svg_path"].startswith("M"))
        self.assertEqual(result.masks[0]["bounds"], {"left": 2, "top": 3, "right": 7, "bottom": 8})
        json.dumps(result.as_dict())
        with Image.open(result.annotated_image) as annotated:
            self.assertEqual(annotated.getpixel((0, 0)), (255, 255, 255))

    async def test_completed_response_with_diagnostics_is_not_valid_geometry(self):
        result = await self.service("<0f>malformed sensitive body\n").segment(self.image, "a box")
        self.assertFalse(result.ok)
        self.assertEqual(result.error["category"], "invalid_geometry")
        self.assertTrue(result.diagnostics)
        self.assertNotIn("sensitive", str(result.as_dict()))

    async def test_empty_completed_lane_means_not_observed_only(self):
        result = await self.service("").segment(self.image, "a box")
        self.assertTrue(result.ok)
        self.assertEqual(result.boxes, [])
        self.assertEqual(result.outcome["observation"], "not_observed")

    async def test_model_mismatch_cannot_claim_valid_geometry(self):
        service = self.service("")
        stream = self.client.responses.stream.return_value
        stream.events[-1]["response"]["model"] = "unexpected-model"
        result = await service.segment(self.image, "a box")
        self.assertFalse(result.ok)
        self.assertEqual(result.error["category"], "invalid_response")

    async def test_plain_text_cannot_be_treated_as_empty_detection(self):
        result = await self.service("sensitive model prose\n").segment(self.image, "a box")
        self.assertFalse(result.ok)
        self.assertNotIn("sensitive", str(result.as_dict()))

    async def test_out_of_source_bounds_is_rejected_without_annotation_request(self):
        text = "<0f>0<|box;x1=12;y1=13;x2=16;y2=17;w=20;h=20|><|mask;x=0;y=0;data=5,5,!!!!!(QO(0lu8?|>\n"
        result = await self.service(text).segment(self.image, "a box")
        self.assertFalse(result.ok)
        self.assertEqual(result.error["category"], "invalid_geometry")


class CliTests(unittest.TestCase):
    def test_transport_cleanup_failure_is_sanitized(self):
        from scripts import test_meta_api as cli
        client = Mock()
        client.close.side_effect = RuntimeError("sensitive provider body during close")
        ping = SimpleNamespace(ok=True, as_dict=lambda: {"ok": True})
        with patch.object(cli.MetaConfig, "from_env", return_value=MetaConfig(api_key="test-only")), \
             patch.object(cli, "create_muse_client", return_value=client), \
             patch.object(cli.MuseSparkService, "ping", return_value=ping), \
             patch.object(cli.sys, "argv", ["test_meta_api.py"]), contextlib.redirect_stdout(io.StringIO()) as output:
            code = cli.main()
        self.assertEqual(code, 1)
        self.assertNotIn("sensitive provider body", output.getvalue())

    def test_cli_missing_image_returns_blocked_and_does_not_print_model_content(self):
        from scripts import test_meta_api as cli
        ping = SimpleNamespace(ok=True, as_dict=lambda: {"ok": True, "response": "sensitive model text"})
        with patch.object(cli.MetaConfig, "from_env", return_value=MetaConfig(api_key="test-only")), \
             patch.object(cli, "create_muse_client", return_value=Mock()), \
             patch.object(cli.MuseSparkService, "ping", return_value=ping), \
             patch.object(cli.sys, "argv", ["test_meta_api.py"]), contextlib.redirect_stdout(io.StringIO()) as output:
            code = cli.main()
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())["sam"]["status"], "BLOCKED")
        self.assertNotIn("sensitive model text", output.getvalue())

    def test_sam_failure_returns_nonzero_and_closes_client_in_request_loop(self):
        from scripts import test_meta_api as cli
        events = []
        class Client:
            async def close(self):
                events.append(("close", asyncio.get_running_loop()))
        async def segment(*args):
            events.append(("request", asyncio.get_running_loop()))
            return SimpleNamespace(ok=False, as_dict=lambda: {"ok": False, "error": {"category": "service_error"}})
        ping = SimpleNamespace(ok=True, as_dict=lambda: {"ok": True})
        with tempfile.TemporaryDirectory() as temporary:
            image = Path(temporary) / "test.png"
            Image.new("RGB", (5, 5), "white").save(image)
            with patch.object(cli.MetaConfig, "from_env", return_value=MetaConfig(api_key="test-only")), \
                 patch.object(cli, "create_muse_client", return_value=Mock()), \
                 patch.object(cli, "create_sam_client", return_value=Client()), \
                 patch.object(cli.MuseSparkService, "ping", return_value=ping), \
                 patch.object(cli.SamSegmentationService, "segment", side_effect=segment), \
                 patch.object(cli.sys, "argv", ["test_meta_api.py", "--image", str(image)]), \
                 contextlib.redirect_stdout(io.StringIO()):
                code = cli.main()
        self.assertEqual(code, 1)
        self.assertEqual([event[0] for event in events], ["request", "close"])
        self.assertIs(events[0][1], events[1][1])


if __name__ == "__main__":
    unittest.main()



