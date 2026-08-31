from __future__ import annotations

import base64
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import getaddresses
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from email_assistant.models import EmailAttachment, RawEmail


GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


class GmailProvider:
    """Gmail API client for reading forwarded PolyU email and sending digests."""

    def __init__(
        self,
        *,
        client_secrets_file: str,
        token_file: str,
        user_id: str = "me",
        expected_account_email: str | None = None,
    ) -> None:
        self.user_id = user_id or "me"
        self.token_file = Path(token_file)
        self._service = build(
            "gmail",
            "v1",
            credentials=_load_credentials(
                client_secrets_file=Path(client_secrets_file),
                token_file=self.token_file,
            ),
        )
        if expected_account_email:
            profile = self.get_profile()
            actual = profile.get("emailAddress", "").lower()
            if actual != expected_account_email.lower():
                raise RuntimeError(
                    "Authenticated Gmail account mismatch: "
                    f"expected {expected_account_email}, got {actual or 'unknown'}."
                )

    def close(self) -> None:
        close = getattr(self._service, "close", None)
        if callable(close):
            close()

    def __enter__(self) -> "GmailProvider":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def get_profile(self) -> dict[str, Any]:
        return self._service.users().getProfile(userId=self.user_id).execute()

    def list_message_ids(self, *, since: datetime, limit: int | None = None) -> list[str]:
        query = f"after:{since.astimezone(timezone.utc).strftime('%Y/%m/%d')}"
        request = self._service.users().messages().list(
            userId=self.user_id,
            q=query,
            maxResults=min(limit or 100, 100),
        )

        ids: list[str] = []
        while request is not None:
            response = request.execute()
            ids.extend(message["id"] for message in response.get("messages", []))
            if limit is not None and len(ids) >= limit:
                return ids[:limit]
            request = self._service.users().messages().list_next(request, response)
        return ids

    def retrieve_email(self, message_id: str) -> RawEmail:
        payload = (
            self._service.users()
            .messages()
            .get(userId=self.user_id, id=message_id, format="full")
            .execute()
        )
        return _raw_email_from_message(payload)

    def fetch_recent_emails(
        self,
        *,
        since: datetime,
        target_email: str | None = None,
        limit: int | None = None,
    ) -> list[RawEmail]:
        emails: list[RawEmail] = []
        for message_id in self.list_message_ids(since=since, limit=None):
            email = self.retrieve_email(message_id)
            if email.created_at and email.created_at < since:
                continue
            if target_email and not email.is_for(target_email):
                continue
            emails.append(email)
            if limit is not None and len(emails) >= limit:
                break
        return emails

    def retrieve_attachment(self, email_id: str, attachment_id: str) -> EmailAttachment:
        email = self.retrieve_email(email_id)
        for attachment in email.attachments:
            if attachment.id == attachment_id:
                return attachment
        raise ValueError(f"Attachment {attachment_id} was not found on Gmail message {email_id}.")

    def download_attachment_bytes(self, email_id: str, attachment: EmailAttachment) -> bytes:
        response = (
            self._service.users()
            .messages()
            .attachments()
            .get(userId=self.user_id, messageId=email_id, id=attachment.id)
            .execute()
        )
        return _urlsafe_b64decode(response.get("data", ""))

    def send_email(
        self,
        *,
        sender: str,
        recipient: str,
        subject: str,
        text: str,
        html: str | None = None,
    ) -> dict[str, Any]:
        message = EmailMessage()
        message["To"] = recipient
        message["From"] = sender
        message["Subject"] = subject
        message.set_content(text)
        if html:
            message.add_alternative(html, subtype="html")

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        return (
            self._service.users()
            .messages()
            .send(userId=self.user_id, body={"raw": raw})
            .execute()
        )


def _load_credentials(*, client_secrets_file: Path, token_file: Path) -> Credentials:
    credentials: Credentials | None = None
    if token_file.exists():
        credentials = Credentials.from_authorized_user_file(str(token_file), GMAIL_SCOPES)

    if credentials and credentials.valid:
        return credentials

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets_file), GMAIL_SCOPES)
        credentials = flow.run_local_server(port=0)

    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(credentials.to_json(), encoding="utf-8")
    return credentials


def _raw_email_from_message(message: dict[str, Any]) -> RawEmail:
    payload = message.get("payload", {})
    headers = _headers(payload.get("headers", []))
    text_parts: list[str] = []
    html_parts: list[str] = []
    attachments: list[EmailAttachment] = []
    _walk_parts(payload, text_parts=text_parts, html_parts=html_parts, attachments=attachments)

    created_at = _datetime_from_internal_date(message.get("internalDate"))
    recipients = _email_addresses(headers.get("to", ""))
    cc = _email_addresses(headers.get("cc", ""))
    bcc = _email_addresses(headers.get("bcc", ""))

    return RawEmail(
        id=message["id"],
        subject=headers.get("subject", ""),
        sender=headers.get("from", ""),
        to=recipients,
        created_at=created_at,
        text="\n\n".join(text_parts).strip() or None,
        html="\n\n".join(html_parts).strip() or None,
        cc=cc,
        bcc=bcc,
        reply_to=_email_addresses(headers.get("reply-to", "")),
        received_for=[*recipients, *cc, *bcc],
        message_id=headers.get("message-id"),
        attachments=attachments,
        headers=headers,
        raw={"threadId": message.get("threadId"), "labelIds": message.get("labelIds", [])},
    )


def _walk_parts(
    part: dict[str, Any],
    *,
    text_parts: list[str],
    html_parts: list[str],
    attachments: list[EmailAttachment],
) -> None:
    mime_type = part.get("mimeType", "")
    body = part.get("body", {})
    data = body.get("data")
    filename = part.get("filename") or None
    headers = _headers(part.get("headers", []))
    attachment_id = body.get("attachmentId")

    if data and mime_type == "text/plain":
        text_parts.append(_urlsafe_b64decode(data).decode("utf-8", errors="replace"))
    elif data and mime_type == "text/html":
        html_parts.append(_urlsafe_b64decode(data).decode("utf-8", errors="replace"))
    elif attachment_id:
        attachments.append(
            EmailAttachment(
                id=attachment_id,
                filename=filename,
                content_type=mime_type or None,
                content_disposition=headers.get("content-disposition"),
                content_id=headers.get("content-id"),
                size=body.get("size"),
            )
        )

    for child in part.get("parts", []) or []:
        _walk_parts(child, text_parts=text_parts, html_parts=html_parts, attachments=attachments)


def _headers(headers: list[dict[str, str]]) -> dict[str, str]:
    return {
        header.get("name", "").lower(): header.get("value", "")
        for header in headers
        if header.get("name")
    }


def _email_addresses(value: str) -> list[str]:
    return [email.lower() for _, email in getaddresses([value]) if email]


def _datetime_from_internal_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        timestamp = int(value) / 1000
    except ValueError:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def _urlsafe_b64decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))
