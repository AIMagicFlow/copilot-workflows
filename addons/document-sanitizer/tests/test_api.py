import base64
import json
import unittest
from unittest import mock

from app import api
from app.config import Settings
from app.extraction.document_intelligence import AnalyzeResult
from app.errors import SanitizerError


class FakeReader:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = 0

    def analyze(self, data, output_format, timeout_seconds):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


def body(file_name="Report.txt", content=b"Acme signed juan@otra.es", **overrides):
    payload = {
        "fileName": file_name,
        "contentType": "text/plain",
        "contentBase64": base64.b64encode(content).decode("ascii"),
        "outputFormat": "markdown",
        "profile": "default-pii",
        "terms": [{"term": "Acme", "replacement": "[CUSTOMER]"}],
        "correlationId": "run-42",
    }
    payload.update(overrides)
    return json.dumps(payload).encode("utf-8")


def handle(raw, settings=None, reader=None):
    return api.handle_sanitize(raw, settings or Settings(), reader, "fallback-id")


def decoded(result):
    return base64.b64decode(result.body["sanitizedContentBase64"]).decode("utf-8")


class HandleSanitizeTests(unittest.TestCase):
    def test_text_file_is_sanitized_with_counts(self):
        result = handle(body())

        self.assertEqual(result.status, 200)
        self.assertEqual(result.body["status"], "completed")
        self.assertEqual(result.body["outputContentType"], "text/markdown; charset=utf-8")
        self.assertEqual(decoded(result), "[CUSTOMER] signed [REDACTED_EMAIL]")
        self.assertEqual(result.body["metadata"]["detectedType"], "txt")
        self.assertEqual(result.body["metadata"]["extractor"], "direct")
        self.assertEqual(result.body["metadata"]["redactionCounts"], {"term": 1, "email": 1, "phone": 0})
        self.assertEqual(result.body["metadata"]["warnings"], [])
        self.assertEqual(result.body["correlationId"], "run-42")

    def test_text_output_format_uses_plain_text_content_type(self):
        result = handle(body(outputFormat="text"))

        self.assertEqual(result.body["outputContentType"], "text/plain; charset=utf-8")

    def test_missing_correlation_id_uses_the_fallback(self):
        payload = json.loads(body())
        del payload["correlationId"]

        result = handle(json.dumps(payload).encode("utf-8"))

        self.assertEqual(result.body["correlationId"], "fallback-id")

    def test_invalid_json_is_400(self):
        result = handle(b"not json")

        self.assertEqual(result.status, 400)
        self.assertEqual(result.body["status"], "failed")
        self.assertEqual(result.body["error"]["code"], "INVALID_REQUEST")

    def test_oversize_file_is_413_before_any_extraction(self):
        reader = FakeReader(AnalyzeResult(content="x", page_count=1))
        settings = Settings(max_file_bytes=4)

        result = handle(body(file_name="scan.pdf", content=b"%PDF-1.7 larger"), settings, reader)

        self.assertEqual(result.status, 413)
        self.assertEqual(result.body["error"]["code"], "FILE_TOO_LARGE")
        self.assertEqual(reader.calls, 0)

    def test_legacy_office_file_is_415(self):
        result = handle(body(file_name="old.doc", content=b"\xd0\xcf\x11\xe0" + b"\x00" * 8))

        self.assertEqual(result.status, 415)
        self.assertEqual(result.body["error"]["code"], "UNSUPPORTED_TYPE")

    def test_blank_text_file_is_422(self):
        result = handle(body(content=b"   \n"))

        self.assertEqual(result.status, 422)
        self.assertEqual(result.body["error"]["code"], "NOT_EXTRACTABLE")

    def test_throttling_is_429_with_retry_after_header(self):
        reader = FakeReader(error=SanitizerError(429, "THROTTLED", "busy", retry_after=7))

        result = handle(body(file_name="scan.pdf", content=b"%PDF-1.7"), reader=reader)

        self.assertEqual(result.status, 429)
        self.assertEqual(result.headers, {"Retry-After": "7"})

    def test_unknown_profile_is_400_before_any_document_call(self):
        reader = FakeReader(AnalyzeResult(content="x", page_count=1))

        result = handle(body(file_name="scan.pdf", content=b"%PDF-1.7", profile="nope"), reader=reader)

        self.assertEqual(result.status, 400)
        self.assertEqual(reader.calls, 0)

    def test_unexpected_failure_is_500_without_input_text(self):
        with mock.patch("app.api.router.extract", side_effect=RuntimeError("secret-marker-9931")):
            result = handle(body())

        self.assertEqual(result.status, 500)
        self.assertEqual(result.body["error"]["code"], "INTERNAL")
        self.assertNotIn("secret-marker-9931", json.dumps(result.body))


if __name__ == "__main__":
    unittest.main()
