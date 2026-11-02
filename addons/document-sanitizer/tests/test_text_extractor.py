import unittest

from app.errors import SanitizerError
from app.extraction.text_extractor import decode


class DecodeTests(unittest.TestCase):
    def test_utf8_bom_is_removed_from_output(self):
        # Review Focus 2: Excel exports carry a BOM that must not reach the output.
        data = b"\xef\xbb\xbfNombre,Empresa\n"

        self.assertEqual(decode(data, "cp1252"), "Nombre,Empresa\n")

    def test_utf16_with_bom_is_decoded(self):
        data = "Acme\n".encode("utf-16")

        self.assertEqual(decode(data, "cp1252"), "Acme\n")

    def test_plain_utf8_is_decoded(self):
        self.assertEqual(decode("Señor Acme".encode("utf-8"), "cp1252"), "Señor Acme")

    def test_fallback_encoding_is_used_when_utf8_fails(self):
        data = "Señor".encode("cp1252")

        self.assertEqual(decode(data, "cp1252"), "Señor")

    def test_undecodable_bytes_are_422(self):
        # 0x81 is undefined in cp1252, so neither UTF-8 nor the fallback can decode it.
        with self.assertRaises(SanitizerError) as ctx:
            decode(b"\x81abc", "cp1252")

        self.assertEqual(ctx.exception.status, 422)
        self.assertEqual(ctx.exception.code, "NOT_EXTRACTABLE")

    def test_blank_text_is_422(self):
        with self.assertRaises(SanitizerError) as ctx:
            decode(b"   \n\t", "cp1252")

        self.assertEqual(ctx.exception.status, 422)
        self.assertEqual(ctx.exception.code, "NOT_EXTRACTABLE")


if __name__ == "__main__":
    unittest.main()
