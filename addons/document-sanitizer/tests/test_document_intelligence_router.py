import io
import unittest
from types import SimpleNamespace

from app.config import Settings
from app.errors import SanitizerError
from app.extraction.document_intelligence import AnalyzeResult, AzureDocumentReader
from app.extraction.router import Extraction, extract
from app.models import SanitizeRequest
from app.type_detection import DetectedType


class FakeReader:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def analyze(self, data, output_format, timeout_seconds):
        self.calls.append((data, output_format, timeout_seconds))
        if self.error is not None:
            raise self.error
        return self.result


def request(output_format="markdown"):
    return SanitizeRequest(
        file_name="doc",
        content_type=None,
        content=b"",
        output_format=output_format,
        profile="default-pii",
        terms=(),
        correlation_id=None,
    )


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings()

    def test_pdf_goes_to_document_intelligence(self):
        reader = FakeReader(AnalyzeResult(content="Texto del PDF", page_count=3))

        result = extract(DetectedType.PDF, b"%PDF-", request(), self.settings, reader)

        self.assertEqual(result, Extraction("Texto del PDF", "document-intelligence-prebuilt-read", 3))
        self.assertEqual(reader.calls, [(b"%PDF-", "markdown", 90)])

    def test_scanned_pdf_without_text_is_422(self):
        # Review Focus 5: no text must not become a 200 with empty content.
        reader = FakeReader(AnalyzeResult(content="   ", page_count=2))

        with self.assertRaises(SanitizerError) as ctx:
            extract(DetectedType.PDF, b"%PDF-", request(), self.settings, reader)

        self.assertEqual(ctx.exception.status, 422)
        self.assertEqual(ctx.exception.code, "NOT_EXTRACTABLE")

    def test_more_pages_than_the_sync_limit_is_413(self):
        reader = FakeReader(AnalyzeResult(content="x", page_count=101))

        with self.assertRaises(SanitizerError) as ctx:
            extract(DetectedType.PDF, b"%PDF-", request(), self.settings, reader)

        self.assertEqual(ctx.exception.status, 413)
        self.assertEqual(ctx.exception.code, "PAGE_LIMIT_EXCEEDED")

    def test_reader_throttling_passes_through(self):
        reader = FakeReader(error=SanitizerError(429, "THROTTLED", "busy", retry_after=7))

        with self.assertRaises(SanitizerError) as ctx:
            extract(DetectedType.PNG, b"\x89PNG", request(), self.settings, reader)

        self.assertEqual(ctx.exception.status, 429)
        self.assertEqual(ctx.exception.retry_after, 7)

    def test_text_types_never_call_the_reader(self):
        reader = FakeReader(AnalyzeResult(content="unused", page_count=1))

        result = extract(DetectedType.CSV, b"Acme,Nombre\n", request(), self.settings, reader)

        self.assertEqual(result, Extraction("Acme,Nombre\n", "direct", None))
        self.assertEqual(reader.calls, [])

    def test_html_uses_the_html_extractor(self):
        result = extract(
            DetectedType.HTML,
            b"<script>x</script><p>Hola</p>",
            request("text"),
            self.settings,
            None,
        )

        self.assertEqual(result, Extraction("Hola", "html-parser", None))

    def test_document_without_a_configured_reader_is_503(self):
        with self.assertRaises(SanitizerError) as ctx:
            extract(DetectedType.DOCX, b"PK", request(), self.settings, None)

        self.assertEqual(ctx.exception.status, 503)
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")


class FakeDiError(Exception):
    def __init__(self, status_code, retry_after=None):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code
        headers = {"Retry-After": str(retry_after)} if retry_after is not None else {}
        self.response = SimpleNamespace(headers=headers)


class FakePoller:
    def __init__(self, result=None, done=True):
        self._result = result
        self._done = done

    def wait(self, timeout=None):
        return None

    def done(self):
        return self._done

    def result(self):
        return self._result


class FakeClient:
    def __init__(self, poller=None, error=None):
        self.poller = poller
        self.error = error
        self.calls = []

    def begin_analyze_document(self, model_id, body, output_content_format):
        self.calls.append((model_id, body.read(), output_content_format))
        if self.error is not None:
            raise self.error
        return self.poller


def di_result(content, pages):
    return SimpleNamespace(content=content, pages=[SimpleNamespace(page_number=i) for i in range(pages)])


class AzureDocumentReaderTests(unittest.TestCase):
    def read(self, client, output_format="markdown", timeout=90):
        reader = AzureDocumentReader("https://example.cognitiveservices.azure.com/", None, client=client)
        return reader.analyze(b"%PDF-", output_format, timeout)

    def test_success_maps_content_and_page_count(self):
        client = FakeClient(poller=FakePoller(di_result("Hola", 2)))

        result = self.read(client, output_format="text")

        self.assertEqual(result, AnalyzeResult(content="Hola", page_count=2))
        self.assertEqual(client.calls, [("prebuilt-read", b"%PDF-", "text")])

    def test_http_429_maps_to_throttled_with_retry_after(self):
        client = FakeClient(error=FakeDiError(429, retry_after=12))

        with self.assertRaises(SanitizerError) as ctx:
            self.read(client)

        self.assertEqual(ctx.exception.status, 429)
        self.assertEqual(ctx.exception.code, "THROTTLED")
        self.assertEqual(ctx.exception.retry_after, 12)

    def test_http_503_maps_to_dependency_unavailable(self):
        client = FakeClient(error=FakeDiError(503))

        with self.assertRaises(SanitizerError) as ctx:
            self.read(client)

        self.assertEqual(ctx.exception.status, 503)
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")

    def test_http_400_maps_to_not_extractable(self):
        client = FakeClient(error=FakeDiError(400))

        with self.assertRaises(SanitizerError) as ctx:
            self.read(client)

        self.assertEqual(ctx.exception.status, 422)
        self.assertEqual(ctx.exception.code, "NOT_EXTRACTABLE")

    def test_other_server_error_maps_to_502(self):
        client = FakeClient(error=FakeDiError(500))

        with self.assertRaises(SanitizerError) as ctx:
            self.read(client)

        self.assertEqual(ctx.exception.status, 502)
        self.assertEqual(ctx.exception.code, "DEPENDENCY_ERROR")

    def test_unfinished_poll_maps_to_504(self):
        client = FakeClient(poller=FakePoller(done=False))

        with self.assertRaises(SanitizerError) as ctx:
            self.read(client)

        self.assertEqual(ctx.exception.status, 504)
        self.assertEqual(ctx.exception.code, "DEPENDENCY_TIMEOUT")


if __name__ == "__main__":
    unittest.main()
