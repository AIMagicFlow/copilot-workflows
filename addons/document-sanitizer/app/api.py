import base64
import logging
import time
from dataclasses import dataclass, field

from . import telemetry
from .config import Settings
from .errors import SanitizerError
from .extraction import router
from .extraction.document_intelligence import DocumentReader
from .models import parse_request
from .normalization import normalize
from .redaction import engine, terms
from .redaction.profiles import get_profile, load_profiles
from .type_detection import detect

LOGGER = logging.getLogger("document_sanitizer")
OUTPUT_CONTENT_TYPES = {
    "markdown": "text/markdown; charset=utf-8",
    "text": "text/plain; charset=utf-8",
}


@dataclass(frozen=True)
class HttpResult:
    status: int
    body: dict
    headers: dict = field(default_factory=dict)


def _error(error: SanitizerError, correlation_id: str) -> HttpResult:
    headers = {"Retry-After": str(error.retry_after)} if error.retry_after is not None else {}
    body = {
        "status": "failed",
        "error": {"code": error.code, "message": error.message},
        "correlationId": correlation_id,
    }
    return HttpResult(error.status, body, headers)


def handle_sanitize(
    body: bytes,
    settings: Settings,
    reader: DocumentReader | None,
    correlation_id_fallback: str,
) -> HttpResult:
    """Run the whole pipeline. Never raises: every failure becomes an HttpResult."""
    started = time.monotonic()
    correlation_id = correlation_id_fallback
    metadata: dict = {}

    def finish(result: HttpResult) -> HttpResult:
        error = result.body.get("error")
        telemetry.log_event(
            LOGGER,
            correlation_id=correlation_id,
            status=result.status,
            durationMs=int((time.monotonic() - started) * 1000),
            errorCode=error["code"] if error else None,
            **metadata,
        )
        return result

    try:
        # Validate everything that is cheap and caller-controlled before any document call.
        request = parse_request(body)
        correlation_id = request.correlation_id or correlation_id_fallback
        metadata["bytes"] = len(request.content)
        rules = terms.build_rules(request.terms)
        profile = get_profile(load_profiles(str(settings.profile_path)), request.profile)

        if len(request.content) > settings.max_file_bytes:
            raise SanitizerError(413, "FILE_TOO_LARGE", "file is larger than the limit")
        detected = detect(request.content, request.file_name, request.content_type)
        metadata["detectedType"] = detected.value
        extraction = router.extract(detected, request.content, request, settings, reader)
        metadata["extractor"] = extraction.extractor
        metadata["pageCount"] = extraction.page_count

        text = normalize(extraction.text)
        if len(text.encode("utf-8")) > settings.max_text_bytes:
            raise SanitizerError(413, "TEXT_TOO_LARGE", "extracted text is larger than the limit")

        redacted = engine.redact(text, rules, profile)
        metadata["redactionCounts"] = redacted.counts
        if engine.still_matches(redacted.text, rules, profile):
            raise SanitizerError(422, "REDACTION_INCOMPLETE", "redaction did not complete")
    except SanitizerError as error:
        return finish(_error(error, correlation_id))
    except Exception:
        # The message is fixed on purpose: an exception text may contain document content.
        return finish(_error(SanitizerError(500, "INTERNAL", "unexpected error"), correlation_id))

    body_out = {
        "status": "completed",
        "outputContentType": OUTPUT_CONTENT_TYPES[request.output_format],
        "sanitizedContentBase64": base64.b64encode(redacted.text.encode("utf-8")).decode("ascii"),
        "metadata": {
            "detectedType": detected.value,
            "extractor": extraction.extractor,
            "pageCount": extraction.page_count,
            "redactionCounts": redacted.counts,
            "warnings": [],
        },
        "correlationId": correlation_id,
    }
    return finish(HttpResult(200, body_out))
