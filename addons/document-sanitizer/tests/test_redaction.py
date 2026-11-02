import json
import tempfile
import unittest
from pathlib import Path

from app.config import DEFAULT_PROFILE_PATH
from app.models import TermIn
from app.redaction import engine, terms
from app.redaction.profiles import get_profile, load_profiles

PROFILE = get_profile(load_profiles(str(DEFAULT_PROFILE_PATH)), "default-pii")


def redact(text, *term_names):
    rules = terms.build_rules([TermIn(term=name, replacement="[CUSTOMER]") for name in term_names])
    return engine.redact(text, rules, PROFILE)


class EmailRuleTests(unittest.TestCase):
    def test_email_addresses_are_redacted(self):
        result = redact("Contacto: juan.perez@acme.es y a+b@sub.example.co.uk")

        self.assertEqual(result.text, "Contacto: [REDACTED_EMAIL] y [REDACTED_EMAIL]")
        self.assertEqual(result.counts["email"], 2)

    def test_non_addresses_are_kept(self):
        for text in ["user@localhost", "@acme", "tool@v1"]:
            with self.subTest(text=text):
                self.assertEqual(redact(text).text, text)


class PhoneRuleTests(unittest.TestCase):
    def test_phone_numbers_are_redacted(self):
        phones = [
            "+34 612 345 678",
            "(555) 123-4567",
            "612-345-678",
            "612.345.678",
            "+1 555 123 4567",
        ]
        for phone in phones:
            with self.subTest(phone=phone):
                result = redact(f"Llame al {phone} hoy")

                self.assertEqual(result.text, "Llame al [REDACTED_PHONE] hoy")
                self.assertEqual(result.counts["phone"], 1)

    def test_digit_runs_without_separators_are_redacted(self):
        # Final review F2: the plan's pattern needed a separator between digit groups.
        result = redact("Tel 612345678 y +34612345678")

        self.assertEqual(result.text, "Tel [REDACTED_PHONE] y [REDACTED_PHONE]")
        self.assertEqual(result.counts["phone"], 2)

    def test_numbers_that_are_not_phones_are_kept(self):
        # Review Focus 3: dates, versions, amounts and identifiers.
        not_phones = [
            "2026-11-02",
            "2026-11-02 10:30",
            "1.2.0.0",
            "1,234.56",
            "12.50",
            "ID 12345",
            "20261102",
        ]
        for text in not_phones:
            with self.subTest(text=text):
                result = redact(text)

                self.assertEqual(result.text, text)
                self.assertEqual(result.counts["phone"], 0)


class OrderAndCountsTests(unittest.TestCase):
    def test_terms_run_before_profile_rules_and_counts_are_separate(self):
        result = redact("Acme escribió a juan@otra.es, tel. +34 612 345 678", "Acme")

        self.assertEqual(
            result.text,
            "[CUSTOMER] escribió a [REDACTED_EMAIL], tel. [REDACTED_PHONE]",
        )
        self.assertEqual(result.counts, {"term": 1, "email": 1, "phone": 1})

    def test_counts_contain_only_integers(self):
        result = redact("Acme juan@acme.es +34 612 345 678", "Acme")

        self.assertTrue(all(isinstance(value, int) for value in result.counts.values()))


class PostCheckTests(unittest.TestCase):
    def test_term_inside_its_own_replacement_does_not_fail_the_check(self):
        # Final review F3: "[ACME]" contains "Acme", which is our output, not a leak.
        rules = terms.build_rules([TermIn("Acme", "[ACME]")])
        result = engine.redact("Acme signed", rules, PROFILE)

        self.assertEqual(result.text, "[ACME] signed")
        self.assertFalse(engine.still_matches(result.text, rules, PROFILE))

    def test_term_inside_another_terms_replacement_does_not_fail_the_check(self):
        rules = terms.build_rules([TermIn("Project", "[PROJECT]"), TermIn("Falcon", "[PROJECT]")])
        result = engine.redact("Falcon review", rules, PROFILE)

        self.assertFalse(engine.still_matches(result.text, rules, PROFILE))

    def test_redacted_text_passes_the_check(self):
        rules = terms.build_rules([TermIn("Acme", "[CUSTOMER]")])
        result = engine.redact("Acme juan@acme.es", rules, PROFILE)

        self.assertFalse(engine.still_matches(result.text, rules, PROFILE))

    def test_a_rule_whose_replacement_matches_its_own_pattern_fails_the_check(self):
        # The replacement "[ABC]" contains "ABC", so a second pass still finds a match.
        profile_file = Path(tempfile.mkdtemp()) / "profiles.json"
        profile_file.write_text(
            json.dumps(
                {
                    "profiles": [
                        {
                            "id": "loop",
                            "rules": [
                                {"id": "abc", "pattern": "ABC", "replacement": "[ABC]", "enabled": True}
                            ],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        profile = get_profile(load_profiles(str(profile_file)), "loop")
        rules = terms.build_rules([])

        result = engine.redact("ABC", rules, profile)

        self.assertTrue(engine.still_matches(result.text, rules, profile))


if __name__ == "__main__":
    unittest.main()
