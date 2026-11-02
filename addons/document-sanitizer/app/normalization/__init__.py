"""Output shaping: Unicode and line-ending normalization, then Markdown or plain text."""

import unicodedata


def normalize(text: str) -> str:
    """NFC Unicode, LF line endings, and no leading byte-order mark. Nothing else changes."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if text.startswith("﻿"):
        text = text[1:]
    return text
