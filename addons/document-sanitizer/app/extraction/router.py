from dataclasses import dataclass

from ..config import Settings
from ..errors import SanitizerError
from ..models import SanitizeRequest
from ..type_detection import DetectedType
from . import text_extractor
from .document_intelligence import DocumentReader
from .html_extractor import extract_html

TEXT_TYPES = {DetectedType.TXT, DetectedType.CSV, DetectedType.MD, DetectedType.JSON, DetectedType.XML, DetectedType.LOG}
DOCUMENT_TYPES = {
    DetectedType.PDF, DetectedType.DOCX, DetectedType.XLSX, DetectedType.PPTX,
    DetectedType.JPEG, DetectedType.PNG, DetectedType.BMP, DetectedType.TIFF, DetectedType.HEIF,
}


@dataclass(frozen=True)
class Extraction:
    text: str
    extractor: str
    page_count: int | None = None


def _require_text(text: str) -> str:
    if not text.strip():
        raise SanitizerError(422, "NOT_EXTRACTABLE", "file contains no text")
    return text


def extract(
    detected: DetectedType,
    data: bytes,
    request: SanitizeRequest,
    settings: Settings,
    reader: DocumentReader | None,
) -> Extraction:
    if detected in TEXT_TYPES:
        text = text_extractor.decode(data, settings.fallback_encoding)
        return Extraction(_require_text(text), "direct")

    if detected is DetectedType.HTML:
        html = text_extractor.decode(data, settings.fallback_encoding)
        text = extract_html(html, request.output_format)
        return Extraction(_require_text(text), "html-parser")

    if detected in DOCUMENT_TYPES:
        if reader is None:
            raise SanitizerError(503, "DEPENDENCY_UNAVAILABLE", "document analysis is not configured")
        result = reader.analyze(data, request.output_format, settings.di_timeout_seconds)
        if result.page_count > settings.max_sync_pages:
            raise SanitizerError(413, "PAGE_LIMIT_EXCEEDED", "document has more pages than the synchronous limit")
        return Extraction(
            _require_text(result.content),
            "document-intelligence-prebuilt-read",
            result.page_count,
        )

    raise SanitizerError(415, "UNSUPPORTED_TYPE", "file type is not supported")
