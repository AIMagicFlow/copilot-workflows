import base64
import binascii
import json
from dataclasses import dataclass

from .errors import SanitizerError

MAX_TERMS = 500
MAX_TERM_CHARS = 200
MAX_REPLACEMENT_CHARS = 50
DEFAULT_REPLACEMENT = "[REDACTED_TERM]"
DEFAULT_PROFILE = "default-pii"
OUTPUT_FORMATS = ("markdown", "text")


@dataclass(frozen=True)
class TermIn:
    term: str
    replacement: str = DEFAULT_REPLACEMENT


@dataclass(frozen=True)
class SanitizeRequest:
    file_name: str
    content_type: str | None
    content: bytes
    output_format: str
    profile: str
    terms: tuple[TermIn, ...]
    correlation_id: str | None


def _invalid(message: str) -> SanitizerError:
    return SanitizerError(400, "INVALID_REQUEST", message)


def _parse_terms(raw) -> tuple[TermIn, ...]:
    if not isinstance(raw, list):
        raise _invalid("terms must be an array")
    if len(raw) > MAX_TERMS:
        raise _invalid(f"at most {MAX_TERMS} terms are allowed")
    terms = []
    for item in raw:
        if not isinstance(item, dict):
            raise _invalid("each term must be an object")
        term = item.get("term")
        if not isinstance(term, str) or not term.strip():
            raise _invalid("each term needs a non-empty term string")
        if len(term) > MAX_TERM_CHARS:
            raise _invalid(f"a term may be at most {MAX_TERM_CHARS} characters")
        replacement = item.get("replacement", DEFAULT_REPLACEMENT)
        if not isinstance(replacement, str) or not replacement or len(replacement) > MAX_REPLACEMENT_CHARS:
            raise _invalid(f"a replacement must be 1 to {MAX_REPLACEMENT_CHARS} characters")
        terms.append(TermIn(term=term, replacement=replacement))
    return tuple(terms)


def parse_request(body: bytes) -> SanitizeRequest:
    try:
        data = json.loads(body)
    except ValueError:  # includes JSONDecodeError and UnicodeDecodeError
        raise _invalid("request body is not valid JSON") from None
    if not isinstance(data, dict):
        raise _invalid("request body must be a JSON object")

    file_name = data.get("fileName")
    if not isinstance(file_name, str) or not file_name.strip():
        raise _invalid("fileName is required")

    content_type = data.get("contentType")
    if content_type is not None and not isinstance(content_type, str):
        raise _invalid("contentType must be a string")

    encoded = data.get("contentBase64")
    if not isinstance(encoded, str) or not encoded:
        raise _invalid("contentBase64 is required")
    try:
        content = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise SanitizerError(400, "INVALID_BASE64", "contentBase64 is not valid Base64") from None

    output_format = data.get("outputFormat", "markdown")
    if output_format not in OUTPUT_FORMATS:
        raise _invalid("outputFormat must be markdown or text")

    profile = data.get("profile", DEFAULT_PROFILE)
    if not isinstance(profile, str) or not profile:
        raise _invalid("profile must be a non-empty string")

    correlation_id = data.get("correlationId")
    if correlation_id is not None and not isinstance(correlation_id, str):
        raise _invalid("correlationId must be a string")

    return SanitizeRequest(
        file_name=file_name,
        content_type=content_type,
        content=content,
        output_format=output_format,
        profile=profile,
        terms=_parse_terms(data.get("terms", [])),
        correlation_id=correlation_id,
    )
