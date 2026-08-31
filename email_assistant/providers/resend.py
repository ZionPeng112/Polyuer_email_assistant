from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from email_assistant.models import EmailAttachment, RawEmail


class ResendProvider:
    """Thin Resend inbound client.

    This provider deliberately has no parsing, classification, or AI logic.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.resend.com",
        timeout: float = 30.0,
    ) -> None:
        self._timeout = timeout
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "ResendProvider":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def list_received_emails(self) -> list[RawEmail]:
        payload = self._get("/emails/receiving")
        items = _data_items(payload)
        return [self._raw_email_from_api(item) for item in items]

    def retrieve_received_email(self, email_id: str, *, html_format: str = "cid") -> RawEmail:
        payload = self._get(f"/emails/receiving/{email_id}", params={"html_format": html_format})
        return self._raw_email_from_api(payload)

    def list_attachments(self, email_id: str) -> list[EmailAttachment]:
        payload = self._get(f"/emails/receiving/{email_id}/attachments")
        items = _data_items(payload)
        return [EmailAttachment.from_api(item) for item in items if isinstance(item, dict)]

    def retrieve_attachment(self, email_id: str, attachment_id: str) -> EmailAttachment:
        payload = self._get(f"/emails/receiving/{email_id}/attachments/{attachment_id}")
        if not isinstance(payload, dict):
            raise RuntimeError(f"Unexpected Resend attachment response shape: {payload}")
        return EmailAttachment.from_api(payload)

    def download_attachment_bytes(self, email_id: str, attachment: EmailAttachment) -> bytes:
        if not attachment.download_url:
            raise ValueError(f"Attachment {attachment.id} has no download_url.")

        response = httpx.get(attachment.download_url, timeout=self._timeout)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            raise RuntimeError(
                f"Resend attachment download failed: {exc.response.status_code} {detail}"
            ) from exc
        return response.content

    def fetch_recent_emails(
        self,
        *,
        since: datetime,
        target_email: str | None = None,
        limit: int | None = None,
    ) -> list[RawEmail]:
        """List recent emails, hydrate each email body, and filter locally.

        Resend's list endpoint returns references without guaranteed body text, so the MVP retrieves
        each candidate by id before handing it to the parser.
        """

        summaries = self.list_received_emails()
        hydrated: list[RawEmail] = []
        for summary in summaries:
            if limit is not None and len(hydrated) >= limit:
                break
            if summary.created_at and summary.created_at < since:
                continue
            if target_email and not summary.is_for(target_email):
                continue
            hydrated_email = self.retrieve_received_email(summary.id)
            if target_email and not hydrated_email.is_for(target_email):
                continue
            if not hydrated_email.attachments:
                hydrated_email = replace(
                    hydrated_email,
                    attachments=self.list_attachments(hydrated_email.id),
                )
            hydrated.append(hydrated_email)
        return hydrated

    def fetch_last_24h(self, *, target_email: str | None = None, limit: int | None = None) -> list[RawEmail]:
        return self.fetch_recent_emails(
            since=datetime.now(timezone.utc) - timedelta(hours=24),
            target_email=target_email,
            limit=limit,
        )

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | list[Any]:
        response = self._client.get(path, params=params)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            raise RuntimeError(f"Resend API request failed: {exc.response.status_code} {detail}") from exc
        return response.json()

    def _raw_email_from_api(self, payload: dict[str, Any]) -> RawEmail:
        return RawEmail(
            id=str(payload["id"]),
            subject=payload.get("subject") or "",
            sender=payload.get("from") or "",
            to=_list_of_strings(payload.get("to")),
            created_at=_parse_datetime(payload.get("created_at")),
            text=payload.get("text"),
            html=payload.get("html"),
            cc=_list_of_strings(payload.get("cc")),
            bcc=_list_of_strings(payload.get("bcc")),
            reply_to=_list_of_strings(payload.get("reply_to")),
            received_for=_list_of_strings(payload.get("received_for")),
            message_id=payload.get("message_id"),
            attachments=[
                EmailAttachment.from_api(item)
                for item in payload.get("attachments", [])
                if isinstance(item, dict)
            ],
            headers=payload.get("headers") or {},
            raw=payload.get("raw"),
        )


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _data_items(payload: dict[str, Any] | list[Any]) -> list[Any]:
    if isinstance(payload, list):
        return payload
    data = payload.get("data", [])
    return data if isinstance(data, list) else []


def _list_of_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result = []
        for item in value:
            if not item:
                continue
            if isinstance(item, dict):
                result.append(str(item.get("email") or item.get("address") or item))
            else:
                result.append(str(item))
        return result
    if isinstance(value, dict):
        return [str(value.get("email") or value.get("address") or value)]
    return [str(value)]
