import io
import zipfile
import zlib
from enum import Enum
from pathlib import PurePath

from .errors import SanitizerError


class DetectedType(str, Enum):
    TXT = "txt"
    CSV = "csv"
    MD = "md"
    JSON = "json"
    XML = "xml"
    LOG = "log"
    HTML = "html"
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    JPEG = "jpeg"
    PNG = "png"
    BMP = "bmp"
    TIFF = "tiff"
    HEIF = "heif"


OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # legacy DOC, XLS, PPT
ZIP_MAGIC = b"PK\x03\x04"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"
TIFF_MAGICS = (b"II*\x00", b"MM\x00*")
HEIF_BRANDS = (b"heic", b"heix", b"mif1", b"msf1")
UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")

TEXT_EXTENSIONS = {
    ".txt": DetectedType.TXT,
    ".csv": DetectedType.CSV,
    ".md": DetectedType.MD,
    ".json": DetectedType.JSON,
    ".xml": DetectedType.XML,
    ".log": DetectedType.LOG,
}
HTML_EXTENSIONS = {".html", ".htm"}
# Types with a binary signature: an extension alone never makes them supported.
BINARY_EXTENSIONS = {
    ".pdf", ".docx", ".xlsx", ".pptx", ".jpg", ".jpeg", ".png", ".bmp",
    ".tif", ".tiff", ".heic", ".heif",
}


def _unsupported() -> SanitizerError:
    return SanitizerError(415, "UNSUPPORTED_TYPE", "file type is not supported")


def _detect_zip(data: bytes) -> DetectedType:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
            if "xl/vbaProject.bin" in names or "[Content_Types].xml" not in names:
                raise _unsupported()
            if b"macroEnabled" in archive.read("[Content_Types].xml"):
                raise _unsupported()
            if any(name.startswith("word/") for name in names):
                return DetectedType.DOCX
            if any(name.startswith("xl/") for name in names):
                return DetectedType.XLSX
            if any(name.startswith("ppt/") for name in names):
                return DetectedType.PPTX
            raise _unsupported()
    except (zipfile.BadZipFile, zlib.error):
        raise SanitizerError(422, "NOT_EXTRACTABLE", "file appears to be corrupt") from None


def detect(data: bytes, file_name: str, content_type: str | None) -> DetectedType:
    """Decide the file type from its bytes first, then its extension.

    content_type is accepted for the caller's hint but does not decide the type.
    """
    ext = PurePath(file_name).suffix.lower()

    if data.startswith(OLE2_MAGIC):
        raise _unsupported()
    if data.startswith(b"%PDF-"):
        return DetectedType.PDF
    if data.startswith(PNG_MAGIC):
        return DetectedType.PNG
    if data.startswith(JPEG_MAGIC):
        return DetectedType.JPEG
    if data.startswith(TIFF_MAGICS):
        return DetectedType.TIFF
    if len(data) >= 12 and data[4:8] == b"ftyp" and data[8:12] in HEIF_BRANDS:
        return DetectedType.HEIF
    if data.startswith(ZIP_MAGIC):
        return _detect_zip(data)
    if ext == ".bmp" and data.startswith(b"BM"):
        return DetectedType.BMP

    if ext in BINARY_EXTENSIONS:
        raise _unsupported()
    if ext in HTML_EXTENSIONS:
        return DetectedType.HTML
    if ext in TEXT_EXTENSIONS:
        if b"\x00" in data and not data.startswith(UTF16_BOMS):
            raise _unsupported()
        return TEXT_EXTENSIONS[ext]
    raise _unsupported()
