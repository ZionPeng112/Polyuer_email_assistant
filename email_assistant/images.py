from __future__ import annotations

import base64
import hashlib
from typing import Protocol

from email_assistant.models import EmailAttachment, HtmlImage, LLMImage, RawEmail


SUPPORTED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}


class AttachmentProvider(Protocol):
    def retrieve_attachment(self, email_id: str, attachment_id: str) -> EmailAttachment:
        ...

    def download_attachment_bytes(self, email_id: str, attachment: EmailAttachment) -> bytes:
        ...


def load_images_for_llm(
    *,
    email: RawEmail,
    provider: AttachmentProvider,
    max_images: int,
    max_bytes: int,
    html_images: list[HtmlImage] | None = None,
    include_remote_urls: bool = False,
) -> list[LLMImage]:
    images: list[LLMImage] = []

    for attachment in email.attachments:
        if len(images) >= max_images:
            break
        if not is_supported_image_attachment(attachment):
            continue
        if attachment.size is not None and attachment.size > max_bytes:
            continue

        hydrated = attachment
        if not hydrated.download_url:
            hydrated = provider.retrieve_attachment(email.id, attachment.id)

        content_type = normalized_content_type(hydrated.content_type)
        if content_type not in SUPPORTED_IMAGE_CONTENT_TYPES:
            continue

        data = provider.download_attachment_bytes(email.id, hydrated)
        if len(data) > max_bytes:
            continue

        images.append(
            LLMImage(
                source="attachment",
                attachment_id=hydrated.id,
                filename=hydrated.filename,
                content_type=content_type,
                size=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                data_url=_data_url(content_type, data),
            )
        )

    if include_remote_urls and html_images:
        for html_image in html_images:
            if len(images) >= max_images:
                break
            if not is_useful_remote_image(html_image):
                continue
            images.append(
                LLMImage(
                    source="remote_html",
                    attachment_id=None,
                    filename=None,
                    content_type=None,
                    size=None,
                    sha256=None,
                    data_url=html_image.src,
                )
            )

    return images


def is_supported_image_attachment(attachment: EmailAttachment) -> bool:
    return normalized_content_type(attachment.content_type) in SUPPORTED_IMAGE_CONTENT_TYPES


def normalized_content_type(content_type: str | None) -> str:
    return (content_type or "").split(";", 1)[0].strip().lower()


def is_useful_remote_image(image: HtmlImage) -> bool:
    src = image.src.strip()
    if not src.startswith(("https://", "http://")):
        return False
    lowered = src.lower()
    if any(marker in lowered for marker in ("track", "pixel", "beacon", "openrate")):
        return False
    return not _looks_like_tiny_pixel(image)


def _looks_like_tiny_pixel(image: HtmlImage) -> bool:
    width = _parse_int(image.width)
    height = _parse_int(image.height)
    if width is None or height is None:
        return False
    return width <= 2 and height <= 2


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _data_url(content_type: str, data: bytes) -> str:
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{content_type};base64,{encoded}"
