import base64
import json
import unittest

from app.errors import SanitizerError
from app.models import DEFAULT_REPLACEMENT, parse_request


def body(**overrides):
    payload = {
        "fileName": "Report.txt",
        "contentType": "text/plain",
        "contentBase64": base64.b64encode(b"Acme signed").decode("ascii"),
        "outputFormat": "markdown",
        "profile": "default-pii",
        "terms": [{"term": "Acme", "replacement": "[CUSTOMER]"}],
        "correlationId": "run-42",
    }
    payload.update(overrides)
    return json.dumps(payload).encode("utf-8")


class ParseRequestTests(unittest.TestCase):
    def test_valid_body_parses(self):
        request = parse_request(body())

        self.assertEqual(request.file_name, "Report.txt")
        self.assertEqual(request.content_type, "text/plain")
        self.assertEqual(request.content, b"Acme signed")
        self.assertEqual(request.output_format, "markdown")
        self.assertEqual(request.profile, "default-pii")
        self.assertEqual(request.terms[0].term, "Acme")
        self.assertEqual(request.terms[0].replacement, "[CUSTOMER]")
        self.assertEqual(request.correlation_id, "run-42")

    def test_defaults_for_optional_fields(self):
        payload = json.loads(body())
        del payload["profile"], payload["outputFormat"], payload["terms"]
        payload["terms"] = [{"term": "Acme"}]

        request = parse_request(json.dumps(payload).encode("utf-8"))

        self.assertEqual(request.profile, "default-pii")
        self.assertEqual(request.output_format, "markdown")
        self.assertEqual(request.terms[0].replacement, DEFAULT_REPLACEMENT)

    def test_invalid_base64_is_400_invalid_base64(self):
        with self.assertRaises(SanitizerError) as ctx:
            parse_request(body(contentBase64="%%%"))

        self.assertEqual(ctx.exception.status, 400)
        self.assertEqual(ctx.exception.code, "INVALID_BASE64")

    def test_more_than_500_terms_is_invalid(self):
        terms = [{"term": f"t{i}"} for i in range(501)]

        with self.assertRaises(SanitizerError) as ctx:
            parse_request(body(terms=terms))

        self.assertEqual(ctx.exception.status, 400)
        self.assertEqual(ctx.exception.code, "INVALID_REQUEST")

    def test_term_over_200_characters_is_invalid(self):
        with self.assertRaises(SanitizerError) as ctx:
            parse_request(body(terms=[{"term": "x" * 201}]))

        self.assertEqual(ctx.exception.code, "INVALID_REQUEST")

    def test_missing_file_name_is_invalid(self):
        payload = json.loads(body())
        del payload["fileName"]

        with self.assertRaises(SanitizerError) as ctx:
            parse_request(json.dumps(payload).encode("utf-8"))

        self.assertEqual(ctx.exception.status, 400)
        self.assertEqual(ctx.exception.code, "INVALID_REQUEST")

    def test_unknown_output_format_is_invalid(self):
        with self.assertRaises(SanitizerError) as ctx:
            parse_request(body(outputFormat="html"))

        self.assertEqual(ctx.exception.code, "INVALID_REQUEST")

    def test_body_that_is_not_json_is_invalid(self):
        with self.assertRaises(SanitizerError) as ctx:
            parse_request(b"not json")

        self.assertEqual(ctx.exception.status, 400)
        self.assertEqual(ctx.exception.code, "INVALID_REQUEST")


if __name__ == "__main__":
    unittest.main()
