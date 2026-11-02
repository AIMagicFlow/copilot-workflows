import unittest

from app.errors import SanitizerError
from app.models import TermIn
from app.redaction import terms

CUSTOMER = "[CUSTOMER]"


def rules_for(*names, replacement=CUSTOMER):
    return terms.build_rules([TermIn(term=name, replacement=replacement) for name in names])


class TermsTests(unittest.TestCase):
    def test_longest_term_wins(self):
        rules = rules_for("Acme", "Acme Corp")

        self.assertEqual(terms.apply("Acme Corp signed", rules), ("[CUSTOMER] signed", 1))

    def test_case_insensitive_matches_are_all_replaced(self):
        rules = rules_for("Acme")

        self.assertEqual(terms.apply("acme and AcMe", rules), ("[CUSTOMER] and [CUSTOMER]", 2))

    def test_word_bounded_match_skips_longer_words(self):
        rules = rules_for("Acme")

        self.assertEqual(terms.apply("Acmeville", rules), ("Acmeville", 0))

    def test_apostrophe_and_hyphen_are_word_boundaries(self):
        rules = rules_for("Acme")

        self.assertEqual(
            terms.apply("Acme's office, Acme-Corp", rules),
            ("[CUSTOMER]'s office, [CUSTOMER]-Corp", 2),
        )

    def test_accented_neighbour_is_not_a_boundary(self):
        # Review Focus 4: "Acmé" is a different word, so "Acme" must not match inside it.
        rules = rules_for("Acme")

        self.assertEqual(terms.apply("Acmé", rules), ("Acmé", 0))

    def test_spanish_term_with_accent_is_replaced(self):
        rules = rules_for("Señor")

        self.assertEqual(terms.apply("Señor Acme", rules), ("[CUSTOMER] Acme", 1))

    def test_regex_metacharacters_are_literal(self):
        # Review Focus 1: a term is never a pattern.
        rules = rules_for("C++ (Ltd.)")

        self.assertEqual(terms.apply("Pay C++ (Ltd.) now", rules), ("Pay [CUSTOMER] now", 1))

    def test_same_term_with_two_replacements_is_invalid(self):
        with self.assertRaises(SanitizerError) as ctx:
            terms.build_rules([TermIn("Acme", "[A]"), TermIn("acme", "[B]")])

        self.assertEqual(ctx.exception.status, 400)
        self.assertEqual(ctx.exception.code, "INVALID_REQUEST")

    def test_blank_term_is_invalid(self):
        with self.assertRaises(SanitizerError) as ctx:
            terms.build_rules([TermIn("   ", "[X]")])

        self.assertEqual(ctx.exception.code, "INVALID_REQUEST")

    def test_no_terms_changes_nothing(self):
        rules = terms.build_rules([])

        self.assertEqual(terms.apply("Acme", rules), ("Acme", 0))
        self.assertFalse(terms.contains("Acme", rules))


if __name__ == "__main__":
    unittest.main()
