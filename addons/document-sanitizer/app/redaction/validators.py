import re

_YEAR_PREFIX = re.compile(r"(?:19|20)\d{2}\b")


def phone_ok(match_text: str) -> bool:
    """Accept a phone-shaped match only if it has 9 to 15 digits.

    A match that starts with a four-digit year and has no leading "+" is a date
    or timestamp, so it is rejected.
    """
    has_plus = match_text.startswith("+")
    digits = re.sub(r"\D", "", match_text)
    if not 9 <= len(digits) <= 15:
        return False
    if not has_plus and _YEAR_PREFIX.match(match_text):
        return False
    return True


VALIDATORS = {
    "phone": phone_ok,
}
