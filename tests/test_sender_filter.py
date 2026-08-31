from email_assistant.models import RawEmail
from email_assistant.sender_filter import (
    clean_forwarded_subject,
    forwarded_sender_address,
    is_allowed_sender,
)


def test_sender_filter_uses_forwarded_sender_header_before_outer_sender():
    email = RawEmail(
        id="1",
        subject="转发: Notice",
        sender='"PENG" <qing-ze.peng@connect.polyu.hk>',
        to=["zionpeng112@gmail.com"],
        created_at=None,
    )
    clean_text = "发件人: Centre <cspse@polyu.edu.hk>\n主题: Notice\nBody"

    assert forwarded_sender_address(clean_text) == "cspse@polyu.edu.hk"
    assert is_allowed_sender(email, ["polyu.edu.hk"], clean_text=clean_text) is True


def test_sender_filter_rejects_non_polyu_sender():
    email = RawEmail(
        id="1",
        subject="Newsletter",
        sender="news@example.com",
        to=["zionpeng112@gmail.com"],
        created_at=None,
    )

    assert is_allowed_sender(email, ["polyu.edu.hk"]) is False


def test_clean_forwarded_subject_strips_repeated_forward_prefixes():
    assert clean_forwarded_subject("转发: Fwd: PolyU Notice") == "PolyU Notice"
