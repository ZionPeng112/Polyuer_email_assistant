import base64

from email_assistant.providers.gmail import _raw_email_from_message


def test_gmail_raw_email_parser_extracts_text_html_and_image_attachment():
    text = base64.urlsafe_b64encode(b"Plain body").decode("ascii").rstrip("=")
    html = base64.urlsafe_b64encode(b"<p>HTML body</p>").decode("ascii").rstrip("=")
    message = {
        "id": "gmail-1",
        "threadId": "thread-1",
        "internalDate": "1798704000000",
        "labelIds": ["INBOX"],
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Test"},
                {"name": "From", "value": "PolyU <notice@example.com>"},
                {"name": "To", "value": "zionpeng112@gmail.com"},
                {"name": "Message-ID", "value": "<message-1@example.com>"},
            ],
            "mimeType": "multipart/mixed",
            "parts": [
                {"mimeType": "text/plain", "body": {"data": text}},
                {"mimeType": "text/html", "body": {"data": html}},
                {
                    "filename": "poster.png",
                    "mimeType": "image/png",
                    "headers": [{"name": "Content-ID", "value": "<poster>"}],
                    "body": {"attachmentId": "att-1", "size": 123},
                },
            ],
        },
    }

    email = _raw_email_from_message(message)

    assert email.id == "gmail-1"
    assert email.subject == "Test"
    assert email.to == ["zionpeng112@gmail.com"]
    assert email.text == "Plain body"
    assert email.html == "<p>HTML body</p>"
    assert email.attachments[0].id == "att-1"
    assert email.attachments[0].content_type == "image/png"
