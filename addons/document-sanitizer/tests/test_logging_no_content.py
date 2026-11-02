import base64
import json
import logging
import unittest
from unittest import mock

from app import api, telemetry
from app.config import Settings

MARKER = "SECRET-MARKER-7731"
EMAIL = "juan@otra.es"


class CaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append(record)


def run(file_name, content):
    body = json.dumps(
        {
            "fileName": file_name,
            "contentBase64": base64.b64encode(content).decode("ascii"),
            "terms": [{"term": "Acme"}],
            "correlationId": "run-1",
        }
    ).encode("utf-8")
    return api.handle_sanitize(body, Settings(), None, "fallback")


class NoContentInLogsTests(unittest.TestCase):
    def setUp(self):
        self.handler = CaptureHandler()
        logging.getLogger().addHandler(self.handler)
        logging.getLogger().setLevel(logging.DEBUG)

    def tearDown(self):
        logging.getLogger().removeHandler(self.handler)

    def assert_no_content(self, forbidden):
        self.assertTrue(self.handler.records, "expected at least one log record")
        for record in self.handler.records:
            rendered = " ".join(
                [record.getMessage(), str(record.args), str(record.exc_text), str(record.__dict__)]
            )
            for text in forbidden:
                self.assertNotIn(text, rendered, f"log record leaked {text!r}")

    def test_success_logs_carry_no_document_text_or_matches(self):
        content = f"Acme {MARKER} {EMAIL}".encode("utf-8")

        result = run(f"{MARKER}.txt", content)

        self.assertEqual(result.status, 200)
        self.assert_no_content([MARKER, "Acme", EMAIL])

    def test_failure_logs_carry_no_file_name_or_content(self):
        result = run(f"{MARKER}.txt", f"   {MARKER}".encode("utf-8")[:3])

        self.assertEqual(result.status, 422)
        self.assert_no_content([MARKER])

    def test_telemetry_is_called_with_allowlisted_fields_only(self):
        allowed = set(telemetry.ALLOWED_FIELDS) | {"correlation_id"}
        with mock.patch.object(telemetry, "log_event", wraps=telemetry.log_event) as spy:
            run("note.txt", f"Acme {MARKER}".encode("utf-8"))

        self.assertEqual(spy.call_count, 1)
        self.assertLessEqual(set(spy.call_args.kwargs), allowed)

    def test_telemetry_rejects_unknown_fields(self):
        with self.assertRaises(ValueError):
            telemetry.log_event(logging.getLogger("t"), correlation_id="x", text="secret")


if __name__ == "__main__":
    unittest.main()
