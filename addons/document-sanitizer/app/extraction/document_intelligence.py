import io
from dataclasses import dataclass
from typing import Protocol

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.exceptions import ServiceResponseTimeoutError

from ..errors import SanitizerError

MODEL_ID = "prebuilt-read"


@dataclass(frozen=True)
class AnalyzeResult:
    content: str
    page_count: int


class DocumentReader(Protocol):
    def analyze(self, data: bytes, output_format: str, timeout_seconds: int) -> AnalyzeResult: ...


def _retry_after(exc: Exception) -> int | None:
    headers = getattr(getattr(exc, "response", None), "headers", None) or {}
    raw = headers.get("Retry-After")
    try:
        return int(raw) if raw is not None else None
    except ValueError:
        return None


def map_error(exc: Exception) -> SanitizerError:
    """Translate a Document Intelligence failure into the design's §4 status codes."""
    if isinstance(exc, (ServiceResponseTimeoutError, TimeoutError)):
        return SanitizerError(504, "DEPENDENCY_TIMEOUT", "document analysis did not finish in time")
    status = getattr(exc, "status_code", None)
    if status == 429:
        return SanitizerError(429, "THROTTLED", "document analysis is throttled", retry_after=_retry_after(exc))
    if status == 503:
        return SanitizerError(503, "DEPENDENCY_UNAVAILABLE", "document analysis is unavailable")
    if status == 400:
        return SanitizerError(422, "NOT_EXTRACTABLE", "the document could not be read")
    return SanitizerError(502, "DEPENDENCY_ERROR", "document analysis failed")


class AzureDocumentReader:
    """prebuilt-read through the managed identity. The client is created on first use."""

    def __init__(self, endpoint: str, credential, client=None):
        self._endpoint = endpoint
        self._credential = credential
        self._client = client

    def _get_client(self):
        if self._client is None:
            self._client = DocumentIntelligenceClient(endpoint=self._endpoint, credential=self._credential)
        return self._client

    def analyze(self, data: bytes, output_format: str, timeout_seconds: int) -> AnalyzeResult:
        client = self._get_client()
        try:
            poller = client.begin_analyze_document(
                MODEL_ID,
                body=io.BytesIO(data),
                output_content_format=output_format,
            )
            poller.wait(timeout_seconds)
            if not poller.done():
                raise TimeoutError("analysis still running after the timeout")
            result = poller.result()
        except Exception as exc:
            raise map_error(exc) from None
        return AnalyzeResult(
            content=result.content or "",
            page_count=len(result.pages or []),
        )
