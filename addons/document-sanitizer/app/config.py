from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

DEFAULT_PROFILE_PATH = Path(__file__).resolve().parent.parent / "config" / "redaction-profiles.json"


@dataclass(frozen=True)
class Settings:
    max_file_bytes: int = 10_485_760
    max_text_bytes: int = 5_242_880
    max_sync_pages: int = 100
    fallback_encoding: str = "cp1252"
    di_timeout_seconds: int = 90
    profile_path: Path = field(default=DEFAULT_PROFILE_PATH)
    document_intelligence_endpoint: str | None = None


def _int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    value = int(raw)  # raises ValueError for non-integers
    if value < 0:
        raise ValueError(f"{name} must not be negative")
    return value


def load_settings(env: Mapping[str, str]) -> Settings:
    profile_path = env.get("SANITIZER_PROFILE_PATH") or DEFAULT_PROFILE_PATH
    return Settings(
        max_file_bytes=_int(env, "SANITIZER_MAX_FILE_BYTES", 10_485_760),
        max_text_bytes=_int(env, "SANITIZER_MAX_TEXT_BYTES", 5_242_880),
        max_sync_pages=_int(env, "SANITIZER_MAX_SYNC_PAGES", 100),
        fallback_encoding=env.get("SANITIZER_FALLBACK_ENCODING") or "cp1252",
        di_timeout_seconds=_int(env, "SANITIZER_DI_TIMEOUT_SECONDS", 90),
        profile_path=Path(profile_path),
        document_intelligence_endpoint=env.get("DOCUMENT_INTELLIGENCE_ENDPOINT") or None,
    )
