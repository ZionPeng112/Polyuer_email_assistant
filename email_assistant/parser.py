from __future__ import annotations

import re
from html import unescape

from bs4 import BeautifulSoup

from email_assistant.models import HtmlImage, ParsedEmail, RawEmail


WHITESPACE_RE = re.compile(r"[ \t\r\f\v]+")
EMPTY_LINES_RE = re.compile(r"\n{3,}")
TRACKING_URL_RE = re.compile(r"https?://\S*(?:utm_[^=\s]+|trk|track|click)\S*", re.IGNORECASE)


def parse_email(email: RawEmail, max_chars: int = 12000) -> ParsedEmail:
    body = email.text or html_to_text(email.html or "")
    return ParsedEmail(
        raw=email,
        clean_text=clean_body(body, max_chars=max_chars),
        html_images=extract_html_images(email.html or ""),
    )


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for img in soup.find_all("img"):
        alt = img.get("alt")
        if alt:
            img.insert_after(f"\n[image: {alt}]\n")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    for block in soup.find_all(["p", "div", "br", "li", "tr", "h1", "h2", "h3"]):
        block.append("\n")

    text = soup.get_text("\n")
    return unescape(text)


def extract_html_images(html: str, *, max_images: int = 50) -> list[HtmlImage]:
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    images: list[HtmlImage] = []
    for img in soup.find_all("img"):
        if len(images) >= max_images:
            break
        src = _attr(img, "src")
        if not src:
            continue
        images.append(
            HtmlImage(
                src=src,
                alt=_attr(img, "alt"),
                title=_attr(img, "title"),
                width=_attr(img, "width"),
                height=_attr(img, "height"),
            )
        )
    return images


def clean_body(body: str, max_chars: int = 12000) -> str:
    body = body.replace("\xa0", " ")
    body = TRACKING_URL_RE.sub("[tracking-link-removed]", body)
    body = "\n".join(_clean_line(line) for line in body.splitlines())
    body = EMPTY_LINES_RE.sub("\n\n", body).strip()

    if len(body) > max_chars:
        return body[:max_chars].rstrip() + "\n[truncated]"
    return body


def _clean_line(line: str) -> str:
    line = line.strip()
    line = WHITESPACE_RE.sub(" ", line)
    return line


def _attr(tag, name: str) -> str | None:
    value = tag.get(name)
    if value is None:
        return None
    text = str(value).strip()
    return text or None
