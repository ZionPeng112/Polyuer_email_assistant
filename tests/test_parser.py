from datetime import datetime, timezone

from email_assistant.models import RawEmail
from email_assistant.parser import parse_email


def test_parse_email_prefers_text_and_normalizes_whitespace():
    email = RawEmail(
        id="email-1",
        subject="Test",
        sender="sender@example.com",
        to=["polyu@faloukulee.resend.app"],
        created_at=datetime.now(timezone.utc),
        text=" Hello   PolyU \n\n\n Please   register. ",
        html="<p>ignored</p>",
    )

    parsed = parse_email(email)

    assert parsed.clean_text == "Hello PolyU\n\nPlease register."


def test_parse_email_converts_html_to_text():
    email = RawEmail(
        id="email-1",
        subject="Test",
        sender="sender@example.com",
        to=["polyu@faloukulee.resend.app"],
        created_at=None,
        html="<html><script>x()</script><body><p>Hello <strong>World</strong></p></body></html>",
    )

    parsed = parse_email(email)

    assert "Hello" in parsed.clean_text
    assert "World" in parsed.clean_text
    assert "x()" not in parsed.clean_text


def test_parse_email_extracts_html_image_metadata_and_alt_text():
    email = RawEmail(
        id="email-1",
        subject="Newsletter",
        sender="sender@example.com",
        to=["polyu@faloukulee.resend.app"],
        created_at=None,
        html='<p>Event</p><img src="https://example.com/poster.png" alt="Seminar poster" width="600">',
    )

    parsed = parse_email(email)

    assert "[image: Seminar poster]" in parsed.clean_text
    assert parsed.html_images[0].src == "https://example.com/poster.png"
    assert parsed.html_images[0].alt == "Seminar poster"
