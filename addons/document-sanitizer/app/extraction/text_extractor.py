import codecs

from ..errors import SanitizerError


def _not_extractable(message: str) -> SanitizerError:
    return SanitizerError(422, "NOT_EXTRACTABLE", message)


def _decode_bytes(data: bytes, fallback_encoding: str) -> str:
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        try:
            return data.decode("utf-16")  # the codec consumes the BOM
        except UnicodeDecodeError:
            raise _not_extractable("text could not be decoded as UTF-16") from None
    if data.startswith(codecs.BOM_UTF8):
        data = data[len(codecs.BOM_UTF8):]
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    try:
        return data.decode(fallback_encoding)
    except UnicodeDecodeError:
        raise _not_extractable("text could not be decoded") from None


def decode(data: bytes, fallback_encoding: str) -> str:
    """Decode a text file to str. The byte-order mark never appears in the result."""
    text = _decode_bytes(data, fallback_encoding)
    if not text.strip():
        raise _not_extractable("file contains no text")
    return text
