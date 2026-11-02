import unittest

from app.normalization import normalize


class NormalizeTests(unittest.TestCase):
    def test_crlf_and_cr_become_lf(self):
        self.assertEqual(normalize("Señor\r\nAcme\r"), "Señor\nAcme\n")

    def test_decomposed_characters_are_composed(self):
        self.assertEqual(normalize("ñ"), "ñ")

    def test_leading_bom_is_removed(self):
        self.assertEqual(normalize("﻿Hola"), "Hola")

    def test_content_is_otherwise_unchanged(self):
        self.assertEqual(normalize("  Acme  \n\n"), "  Acme  \n\n")


if __name__ == "__main__":
    unittest.main()
