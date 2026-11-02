from dataclasses import dataclass

from ..errors import SanitizerError
from . import terms
from .profiles import Profile, Rule
from .terms import TermRules
from .validators import VALIDATORS

REGEX_TIMEOUT_SECONDS = 2


@dataclass(frozen=True)
class RedactionResult:
    text: str
    counts: dict[str, int]


def _matches(rule: Rule, text: str) -> list:
    """Accepted matches for one rule. Raises TimeoutError if the pattern runs too long."""
    check = VALIDATORS[rule.validator] if rule.validator else None
    found = rule.pattern.finditer(text, timeout=REGEX_TIMEOUT_SECONDS)
    matches = []
    for match in found:
        if check is None or check(match.group(0)):
            matches.append(match)
    return matches


def _replace(rule: Rule, text: str) -> tuple[str, int]:
    pieces = []
    last = 0
    matches = _matches(rule, text)
    for match in matches:
        pieces.append(text[last:match.start()])
        pieces.append(rule.replacement)
        last = match.end()
    pieces.append(text[last:])
    return "".join(pieces), len(matches)


def redact(text: str, term_rules: TermRules, profile: Profile) -> RedactionResult:
    text, term_count = terms.apply(text, term_rules)
    counts = {"term": term_count}
    try:
        for rule in profile.rules:
            if rule.enabled:
                text, counts[rule.id] = _replace(rule, text)
    except TimeoutError:
        # Fail closed: a rule that cannot finish releases no text.
        raise SanitizerError(422, "REDACTION_INCOMPLETE", "redaction did not complete") from None
    return RedactionResult(text=text, counts=counts)


def _mask_term_replacements(text: str, term_rules: TermRules) -> str:
    """Blank out the caller's replacements so a term inside one is not reported as a leak.

    Profile replacements are not masked: a rule whose replacement matches its own
    pattern is a configuration error and must still fail the check.
    """
    for replacement in sorted(set(term_rules.replacements), key=len, reverse=True):
        text = text.replace(replacement, " ")
    return text


def still_matches(text: str, term_rules: TermRules, profile: Profile) -> bool:
    """The post-redaction check. True means some term or rule still finds a match."""
    unmasked = _mask_term_replacements(text, term_rules)
    if terms.contains(unmasked, term_rules):
        return True
    for rule in profile.rules:
        if not rule.enabled:
            continue
        try:
            if _matches(rule, unmasked):
                return True
        except TimeoutError:
            return True
    return False
