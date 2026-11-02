import json
import tempfile
import unittest
from pathlib import Path

from app.config import DEFAULT_PROFILE_PATH
from app.errors import SanitizerError
from app.redaction.profiles import get_profile, load_profiles


def write_profile(rules):
    path = Path(tempfile.mkdtemp()) / "profiles.json"
    path.write_text(
        json.dumps({"profiles": [{"id": "test", "rules": rules}]}),
        encoding="utf-8",
    )
    return str(path)


def rule(**overrides):
    base = {"id": "r", "pattern": "abc", "replacement": "[R]", "enabled": True}
    base.update(overrides)
    return base


class ProfileLoadTests(unittest.TestCase):
    def test_shipped_profile_loads_with_email_and_phone(self):
        profiles = load_profiles(str(DEFAULT_PROFILE_PATH))
        profile = get_profile(profiles, "default-pii")

        self.assertEqual([r.id for r in profile.rules], ["email", "phone"])
        self.assertEqual(profile.rules[0].replacement, "[REDACTED_EMAIL]")
        self.assertEqual(profile.rules[1].replacement, "[REDACTED_PHONE]")

    def test_nested_quantifier_is_rejected(self):
        with self.assertRaises(SanitizerError) as ctx:
            load_profiles(write_profile([rule(pattern="(a+)+$")]))

        self.assertEqual(ctx.exception.status, 500)

    def test_pattern_that_does_not_compile_is_rejected(self):
        with self.assertRaises(SanitizerError):
            load_profiles(write_profile([rule(pattern="(unclosed")]))

    def test_replacement_without_brackets_is_rejected(self):
        with self.assertRaises(SanitizerError):
            load_profiles(write_profile([rule(replacement="REDACTED")]))

    def test_unknown_validator_is_rejected(self):
        with self.assertRaises(SanitizerError):
            load_profiles(write_profile([rule(validator="nope")]))

    def test_unknown_profile_id_is_400(self):
        profiles = load_profiles(str(DEFAULT_PROFILE_PATH))

        with self.assertRaises(SanitizerError) as ctx:
            get_profile(profiles, "missing")

        self.assertEqual(ctx.exception.status, 400)
        self.assertEqual(ctx.exception.code, "INVALID_REQUEST")


if __name__ == "__main__":
    unittest.main()
