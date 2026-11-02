from bs4 import BeautifulSoup


def soup_to_text(soup: BeautifulSoup) -> str:
    """Visible text of a cleaned soup: one non-empty line per text line, LF endings."""
    lines = (line.strip() for line in soup.get_text("\n").splitlines())
    return "\n".join(line for line in lines if line)
