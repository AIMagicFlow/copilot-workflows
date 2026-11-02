import re
import unicodedata
from dataclasses import dataclass
from typing import Sequence

from ..errors import SanitizerError
from ..models import TermIn


@dataclass(frozen=True)
class TermRules:
    # One named group per term: group t{i} matches term i, whose replacement is replacements[i].
    pattern: "re.Pattern | None"
    replacements: tuple[str, ...]


def build_rules(terms: Sequence[TermIn]) -> TermRules:
    by_key: dict[str, tuple[str, str]] = {}
    for item in terms:
        term = unicodedata.normalize("NFC", item.term).strip()
        if not term:
            raise SanitizerError(400, "INVALID_REQUEST", "terms must not be blank")
        key = term.casefold()
        if key in by_key:
            if by_key[key][1] != item.replacement:
                raise SanitizerError(400, "INVALID_REQUEST", "the same term has two replacements")
            continue
        by_key[key] = (term, item.replacement)

    if not by_key:
        return TermRules(None, ())

    # Longest first, so "Acme Corp" is tried before "Acme" at the same position.
    ordered = sorted(by_key.values(), key=lambda pair: len(pair[0]), reverse=True)
    alternatives = "|".join(
        f"(?P<t{index}>{re.escape(term)})" for index, (term, _) in enumerate(ordered)
    )
    pattern = re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", re.IGNORECASE)
    return TermRules(pattern, tuple(replacement for _, replacement in ordered))


def apply(text: str, rules: TermRules) -> tuple[str, int]:
    if rules.pattern is None:
        return text, 0
    return rules.pattern.subn(
        lambda match: rules.replacements[int(match.lastgroup[1:])],
        text,
    )


def contains(text: str, rules: TermRules) -> bool:
    return rules.pattern is not None and rules.pattern.search(text) is not None
