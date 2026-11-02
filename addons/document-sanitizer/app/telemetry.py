import logging

# Metadata only (design §7). Content, file names and matches are never allowed here.
ALLOWED_FIELDS = (
    "detectedType",
    "extractor",
    "bytes",
    "durationMs",
    "status",
    "pageCount",
    "redactionCounts",
    "errorCode",
)


def _render(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, dict):
        return ",".join(f"{key}:{count}" for key, count in value.items()) or "-"
    return str(value)


def log_event(logger: logging.Logger, *, correlation_id: str, **fields) -> None:
    unknown = sorted(set(fields) - set(ALLOWED_FIELDS))
    if unknown:
        raise ValueError(f"not allowed in logs: {', '.join(unknown)}")
    parts = [f"correlationId={_render(correlation_id)}"]
    parts += [f"{name}={_render(fields[name])}" for name in ALLOWED_FIELDS if name in fields]
    logger.info("sanitize %s", " ".join(parts))
