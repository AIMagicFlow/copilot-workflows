import io
import unittest
import zipfile

from app.errors import SanitizerError
from app.type_detection import DetectedType, detect


def zip_bytes(names, extra=None):
    files = {name: "x" for name in names}
    files.update(extra or {})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


OOXML_CONTENT_TYPES = "[Content_Types].xml"


class DetectTypeTests(unittest.TestCase):
    def test_text_extensions_are_detected(self):
        cases = {
            "notes.txt": DetectedType.TXT,
            "data.csv": DetectedType.CSV,
            "readme.md": DetectedType.MD,
            "payload.json": DetectedType.JSON,
            "feed.xml": DetectedType.XML,
            "run.log": DetectedType.LOG,
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                self.assertIs(detect(b"Acme,Nombre\n", name, None), expected)

    def test_html_by_extension(self):
        self.assertIs(detect(b"<p>hola</p>", "page.htm", None), DetectedType.HTML)
        self.assertIs(detect(b"<p>hola</p>", "page.html", None), DetectedType.HTML)

    def test_pdf_by_signature(self):
        self.assertIs(detect(b"%PDF-1.7\n%...", "scan.pdf", None), DetectedType.PDF)

    def test_images_by_signature(self):
        self.assertIs(detect(b"\x89PNG\r\n\x1a\n....", "x.png", None), DetectedType.PNG)
        self.assertIs(detect(b"\xff\xd8\xff\xe0....", "x.jpg", None), DetectedType.JPEG)
        self.assertIs(detect(b"II*\x00....", "x.tif", None), DetectedType.TIFF)
        self.assertIs(detect(b"MM\x00*....", "x.tiff", None), DetectedType.TIFF)
        self.assertIs(detect(b"BM....", "x.bmp", None), DetectedType.BMP)
        heif = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 8
        self.assertIs(detect(heif, "x.heic", None), DetectedType.HEIF)

    def test_office_files_by_zip_content(self):
        docx = zip_bytes([OOXML_CONTENT_TYPES, "word/document.xml"])
        xlsx = zip_bytes([OOXML_CONTENT_TYPES, "xl/workbook.xml"])
        pptx = zip_bytes([OOXML_CONTENT_TYPES, "ppt/presentation.xml"])

        self.assertIs(detect(docx, "a.docx", None), DetectedType.DOCX)
        self.assertIs(detect(xlsx, "a.xlsx", None), DetectedType.XLSX)
        self.assertIs(detect(pptx, "a.pptx", None), DetectedType.PPTX)

    def test_content_type_hint_does_not_change_the_result(self):
        self.assertIs(
            detect(b"%PDF-1.4", "scan.pdf", "application/octet-stream"),
            DetectedType.PDF,
        )

    def test_legacy_office_is_415(self):
        ole2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 16

        with self.assertRaises(SanitizerError) as ctx:
            detect(ole2, "old.doc", None)

        self.assertEqual(ctx.exception.status, 415)
        self.assertEqual(ctx.exception.code, "UNSUPPORTED_TYPE")

    def test_macro_enabled_office_is_415(self):
        xlsm = zip_bytes(
            [OOXML_CONTENT_TYPES, "xl/workbook.xml", "xl/vbaProject.bin"],
        )

        with self.assertRaises(SanitizerError) as ctx:
            detect(xlsm, "book.xlsm", None)

        self.assertEqual(ctx.exception.code, "UNSUPPORTED_TYPE")

    def test_macro_enabled_content_type_is_415(self):
        docm = zip_bytes(
            [OOXML_CONTENT_TYPES, "word/document.xml"],
            extra={OOXML_CONTENT_TYPES: "application/vnd.ms-word.document.macroEnabled.main+xml"},
        )

        with self.assertRaises(SanitizerError) as ctx:
            detect(docm, "macro.docx", None)

        self.assertEqual(ctx.exception.code, "UNSUPPORTED_TYPE")

    def test_text_with_nul_byte_is_415(self):
        with self.assertRaises(SanitizerError) as ctx:
            detect(b"abc\x00def", "notes.txt", None)

        self.assertEqual(ctx.exception.status, 415)

    def test_utf16_text_with_bom_is_text(self):
        utf16 = "Acme\n".encode("utf-16")

        self.assertIs(detect(utf16, "export.csv", None), DetectedType.CSV)

    def test_executable_is_415(self):
        with self.assertRaises(SanitizerError) as ctx:
            detect(b"MZ\x90\x00", "tool.exe", None)

        self.assertEqual(ctx.exception.status, 415)

    def test_pdf_extension_with_text_content_is_415(self):
        with self.assertRaises(SanitizerError) as ctx:
            detect(b"just some words", "scan.pdf", None)

        self.assertEqual(ctx.exception.status, 415)

    def test_corrupt_zip_is_422(self):
        with self.assertRaises(SanitizerError) as ctx:
            detect(b"PK\x03\x04 truncated", "broken.docx", None)

        self.assertEqual(ctx.exception.status, 422)
        self.assertEqual(ctx.exception.code, "NOT_EXTRACTABLE")

    def test_unknown_extension_is_415(self):
        with self.assertRaises(SanitizerError) as ctx:
            detect(b"hello", "file.weird", None)

        self.assertEqual(ctx.exception.status, 415)


if __name__ == "__main__":
    unittest.main()
