from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class EmailCategory(StrEnum):
    MUST_ACTION = "MUST_ACTION"
    MUST_ATTEND = "MUST_ATTEND"
    ACADEMIC_NOTICE = "ACADEMIC_NOTICE"
    OPTIONAL_EVENT = "OPTIONAL_EVENT"
    GENERAL = "GENERAL"


class Importance(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass(frozen=True)
class EmailAttachment:
    id: str
    filename: str | None = None
    content_type: str | None = None
    content_disposition: str | None = None
    content_id: str | None = None
    size: int | None = None
    download_url: str | None = None
    expires_at: datetime | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "EmailAttachment":
        return cls(
            id=str(payload.get("id", "")),
            filename=payload.get("filename"),
            content_type=payload.get("content_type"),
            content_disposition=payload.get("content_disposition"),
            content_id=payload.get("content_id"),
            size=payload.get("size"),
            download_url=payload.get("download_url"),
            expires_at=_parse_datetime(payload.get("expires_at")),
        )


@dataclass(frozen=True)
class RawEmail:
    id: str
    subject: str
    sender: str
    to: list[str]
    created_at: datetime | None
    text: str | None = None
    html: str | None = None
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    reply_to: list[str] = field(default_factory=list)
    received_for: list[str] = field(default_factory=list)
    message_id: str | None = None
    attachments: list[EmailAttachment] = field(default_factory=list)
    headers: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] | None = None

    def all_recipients(self) -> set[str]:
        values = [*self.to, *self.cc, *self.bcc, *self.received_for]
        return {value.lower() for value in values if value}

    def is_for(self, target_email: str) -> bool:
        return target_email.lower() in self.all_recipients()


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@dataclass(frozen=True)
class ParsedEmail:
    raw: RawEmail
    clean_text: str
    html_images: list["HtmlImage"] = field(default_factory=list)


@dataclass(frozen=True)
class HtmlImage:
    src: str
    alt: str | None = None
    title: str | None = None
    width: str | None = None
    height: str | None = None


@dataclass(frozen=True)
class LLMImage:
    source: str
    attachment_id: str | None
    filename: str | None
    content_type: str | None
    size: int | None
    sha256: str | None
    data_url: str


@dataclass(frozen=True)
class EmailAnalysis:
    email_id: str
    category: EmailCategory
    importance: Importance
    summary: str
    mandatory: bool
    action_required: bool
    action: str | None
    deadline: str | None
    event_time: str | None
    location: str | None
    evidence: str | None
    confidence: float
    subject: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["category"] = self.category.value
        data["importance"] = self.importance.value
        return data
