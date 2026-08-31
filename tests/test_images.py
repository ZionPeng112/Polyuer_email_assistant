import httpx

from email_assistant.images import is_supported_image_attachment, load_images_for_llm
from email_assistant.models import EmailAttachment, HtmlImage, RawEmail


class FakeAttachmentProvider:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def retrieve_attachment(self, email_id: str, attachment_id: str) -> EmailAttachment:
        return EmailAttachment(
            id=attachment_id,
            filename="poster.png",
            content_type="image/png",
            download_url="https://example.com/poster.png",
        )

    def download_attachment_bytes(self, email_id: str, attachment: EmailAttachment) -> bytes:
        return self.data


def test_load_images_for_llm_builds_data_url_without_persisting_bytes():
    email = RawEmail(
        id="email-1",
        subject="Poster",
        sender="school@example.com",
        to=["polyu@faloukulee.resend.app"],
        created_at=None,
        attachments=[
            EmailAttachment(
                id="att-1",
                filename="poster.png",
                content_type="image/png",
                size=3,
            )
        ],
    )

    images = load_images_for_llm(
        email=email,
        provider=FakeAttachmentProvider(b"abc"),
        max_images=4,
        max_bytes=100,
    )

    assert len(images) == 1
    assert images[0].data_url == "data:image/png;base64,YWJj"
    assert images[0].sha256


def test_image_attachment_detection_rejects_non_images():
    assert is_supported_image_attachment(EmailAttachment(id="1", content_type="application/pdf")) is False
    assert is_supported_image_attachment(EmailAttachment(id="2", content_type="image/jpeg")) is True


def test_load_images_for_llm_downloads_remote_html_images(monkeypatch):
    def fake_get(*args, **kwargs):
        return httpx.Response(
            200,
            headers={"content-type": "image/png"},
            content=b"abc",
            request=httpx.Request("GET", "https://example.com/poster.png"),
        )

    monkeypatch.setattr("email_assistant.images.httpx.get", fake_get)
    email = RawEmail(
        id="email-1",
        subject="Poster",
        sender="school@example.com",
        to=["polyu@faloukulee.resend.app"],
        created_at=None,
    )

    images = load_images_for_llm(
        email=email,
        provider=FakeAttachmentProvider(b"abc"),
        max_images=4,
        max_bytes=100,
        html_images=[
            HtmlImage(
                src="https://example.com/poster.png",
                alt="Poster",
            )
        ],
        include_remote_urls=True,
    )

    assert images[0].source == "remote_html"
    assert images[0].data_url == "data:image/png;base64,YWJj"
    assert images[0].content_type == "image/png"
    assert images[0].sha256
