import httpx

from email_assistant.providers.resend import ResendProvider


def test_resend_provider_lists_and_retrieves_attachments():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer re_test"
        if request.url.path == "/emails/receiving/email-1/attachments":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "att-1",
                            "filename": "file.pdf",
                            "size": 123,
                            "content_type": "application/pdf",
                        }
                    ]
                },
            )
        if request.url.path == "/emails/receiving/email-1/attachments/att-1":
            return httpx.Response(
                200,
                json={
                    "id": "att-1",
                    "filename": "file.pdf",
                    "download_url": "https://example.com/file.pdf",
                    "expires_at": "2026-10-17T14:29:41.521Z",
                },
            )
        return httpx.Response(404)

    provider = ResendProvider("re_test")
    provider._client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.resend.com",
        headers={"Authorization": "Bearer re_test"},
    )

    attachments = provider.list_attachments("email-1")
    attachment = provider.retrieve_attachment("email-1", "att-1")

    assert attachments[0].filename == "file.pdf"
    assert attachment.download_url == "https://example.com/file.pdf"
