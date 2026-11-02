from typing import Literal

from bs4 import BeautifulSoup, Comment

from ..normalization.markdown import html_to_markdown
from ..normalization.plain_text import soup_to_text

DROPPED_TAGS = ("script", "style", "noscript", "template")


def _is_hidden(tag) -> bool:
    if tag.has_attr("hidden") or tag.get("aria-hidden") == "true":
        return True
    style = (tag.get("style") or "").replace(" ", "").lower()
    return "display:none" in style or "visibility:hidden" in style


def _clean(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for comment in soup.find_all(string=lambda node: isinstance(node, Comment)):
        comment.extract()
    for tag in soup.find_all(DROPPED_TAGS):
        tag.extract()
    for tag in soup.find_all(_is_hidden):
        tag.extract()  # extract, not decompose: a hidden parent may already be detached
    return soup


def extract_html(html: str, output_format: Literal["markdown", "text"]) -> str:
    soup = _clean(html)
    if output_format == "markdown":
        return html_to_markdown(str(soup))
    return soup_to_text(soup)
