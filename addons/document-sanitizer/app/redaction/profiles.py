import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Mapping

import regex

from ..errors import SanitizerError
from .validators import VALIDATORS

PLACEHOLDER = re.compile(r"\[[A-Z_]+\]")
# A group that contains a quantifier and is itself quantified, such as (a+)+ or (a*)*.
NESTED_QUANTIFIER = re.compile(r"\([^()]*[+*][^()]*\)(?:[+*]|\{\d*,?\d*\})")


@dataclass(frozen=True)
class Rule:
    id: str
    pattern: "regex.Pattern"
    replacement: str
    enabled: bool
    validator: str | None


@dataclass(frozen=True)
class Profile:
    id: str
    rules: tuple[Rule, ...]


def _config_error(message: str) -> SanitizerError:
    return SanitizerError(500, "INTERNAL", f"redaction profile configuration is invalid: {message}")


def _parse_rule(raw) -> Rule:
    if not isinstance(raw, dict):
        raise _config_error("a rule must be an object")
    rule_id = raw.get("id")
    if not isinstance(rule_id, str) or not rule_id:
        raise _config_error("a rule needs an id")
    source = raw.get("pattern")
    if not isinstance(source, str) or not source:
        raise _config_error(f"rule {rule_id} needs a pattern")
    if NESTED_QUANTIFIER.search(source):
        raise _config_error(f"rule {rule_id} has a nested quantifier")
    try:
        compiled = regex.compile(source)
    except regex.error:
        raise _config_error(f"rule {rule_id} does not compile") from None
    replacement = raw.get("replacement")
    if not isinstance(replacement, str) or not PLACEHOLDER.fullmatch(replacement):
        raise _config_error(f"rule {rule_id} needs a bracketed placeholder replacement")
    validator = raw.get("validator")
    if validator is not None and validator not in VALIDATORS:
        raise _config_error(f"rule {rule_id} names an unknown validator")
    return Rule(
        id=rule_id,
        pattern=compiled,
        replacement=replacement,
        enabled=bool(raw.get("enabled", True)),
        validator=validator,
    )


@lru_cache(maxsize=4)
def load_profiles(path: str) -> Mapping[str, Profile]:
    """Load and validate every profile in the file. Results are cached per path."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        raise _config_error("the file cannot be read") from None
    if not isinstance(data, dict) or not isinstance(data.get("profiles"), list):
        raise _config_error("the file needs a profiles array")

    profiles: dict[str, Profile] = {}
    for raw in data["profiles"]:
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str) or not raw["id"]:
            raise _config_error("each profile needs an id")
        rules = tuple(_parse_rule(item) for item in raw.get("rules", []))
        profiles[raw["id"]] = Profile(id=raw["id"], rules=rules)
    return profiles


def get_profile(profiles: Mapping[str, Profile], profile_id: str) -> Profile:
    profile = profiles.get(profile_id)
    if profile is None:
        raise SanitizerError(400, "INVALID_REQUEST", "unknown profile")
    return profile
