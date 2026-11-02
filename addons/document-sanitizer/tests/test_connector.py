import json
import re
import unittest
from pathlib import Path

DEFINITION = Path(__file__).resolve().parent.parent / "connector" / "apiDefinition.swagger.json"
EXPECTED_RESPONSES = {"200", "400", "401", "403", "413", "415", "422", "429", "500", "502", "503", "504"}
SECRET_LIKE = re.compile(r"[A-Za-z0-9+/=_-]{32,}")


class ConnectorDefinitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = DEFINITION.read_text(encoding="utf-8")
        cls.doc = json.loads(cls.raw)

    def test_is_swagger_2(self):
        self.assertEqual(self.doc["swagger"], "2.0")

    def test_api_key_is_sent_in_the_functions_key_header(self):
        scheme = self.doc["securityDefinitions"]["api_key"]

        self.assertEqual(scheme, {"type": "apiKey", "in": "header", "name": "x-functions-key"})
        self.assertEqual(self.doc["security"], [{"api_key": []}])

    def test_operation_is_post_to_the_v1_route(self):
        operation = self.doc["paths"]["/api/v1/documents/sanitize"]["post"]

        self.assertEqual(operation["operationId"], "SanitizeDocument")

    def test_terms_are_capped_at_500(self):
        body = self.doc["paths"]["/api/v1/documents/sanitize"]["post"]["parameters"][0]["schema"]
        terms = body["properties"]["terms"]

        self.assertEqual(terms["maxItems"], 500)
        self.assertEqual(terms["items"]["properties"]["term"]["maxLength"], 200)
        self.assertEqual(terms["items"]["properties"]["replacement"]["maxLength"], 50)

    def test_documents_every_status_in_the_design(self):
        responses = set(self.doc["paths"]["/api/v1/documents/sanitize"]["post"]["responses"])

        self.assertEqual(responses, EXPECTED_RESPONSES)

    def test_no_key_like_literal_is_committed(self):
        self.assertIsNone(SECRET_LIKE.search(self.raw))

    def test_host_is_a_placeholder(self):
        self.assertEqual(self.doc["host"], "your-sanitizer.azurewebsites.net")


if __name__ == "__main__":
    unittest.main()
