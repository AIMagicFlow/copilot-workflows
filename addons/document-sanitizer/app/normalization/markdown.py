from markdownify import markdownify


def html_to_markdown(html: str) -> str:
    """Markdown for an already-cleaned HTML fragment, with ATX headings."""
    # Underscores and asterisks stay as written: escaping them would split terms and emails.
    return markdownify(
        html,
        heading_style="ATX",
        escape_underscores=False,
        escape_asterisks=False,
    ).strip()
