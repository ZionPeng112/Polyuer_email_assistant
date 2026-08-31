from __future__ import annotations

from email.utils import parseaddr
import re

from email_assistant.models import RawEmail


FORWARDED_SENDER_RE = re.compile(
    r"^(?:发件人|寄件者|from)\s*[:：]\s*(?P<value>.+)$",
    re.IGNORECASE | re.MULTILINE,
)


def is_allowed_sender(email: RawEmail, allowed_domains: list[str], *, clean_text: str = "") -> bool:
    if not allowed_domains:
        return True

    sender_address = forwarded_sender_address(clean_text) or parseaddr(email.sender)[1].lower()
    if "@" not in sender_address:
        return False

    domain = sender_address.rsplit("@", 1)[1]
    return any(domain == allowed or domain.endswith(f".{allowed}") for allowed in allowed_domains)


def forwarded_sender_address(clean_text: str) -> str | None:
    match = FORWARDED_SENDER_RE.search(clean_text)
    if not match:
        return None
    address = parseaddr(match.group("value"))[1].lower()
    return address or None


def clean_forwarded_subject(subject: str) -> str:
    cleaned = subject.strip()
    prefixes = ("转发:", "转发：", "轉發:", "轉發：", "fw:", "fwd:", "fw：", "fwd：")
    changed = True
    while changed:
        changed = False
        lowered = cleaned.lower()
        for prefix in prefixes:
            if lowered.startswith(prefix):
                cleaned = cleaned[len(prefix) :].strip()
                changed = True
                break
    return cleaned or subject.strip()
