from __future__ import annotations

import argparse
import json
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Iterator
from zoneinfo import ZoneInfo

from email_assistant.analyzer import EmailAnalyzer
from email_assistant.config import AppConfig
from email_assistant.database import EmailDatabase
from email_assistant.digest import build_daily_digest, build_daily_digest_zh
from email_assistant.images import is_supported_image_attachment, load_images_for_llm
from email_assistant.parser import parse_email
from email_assistant.providers.gmail import GmailProvider
from email_assistant.providers.n1n import N1NLLMProvider
from email_assistant.providers.resend import ResendProvider
from email_assistant.sender_filter import clean_forwarded_subject, is_allowed_sender


def main() -> None:
    args = _parse_args()
    config = AppConfig.from_env()

    if args.command == "fetch-test":
        _fetch_test(config, limit=args.limit)
    elif args.command == "process":
        window = _window_from_args(args, config)
        _process(
            config,
            window=window,
            limit=args.limit,
            dry_run=args.dry_run,
            force=args.force,
        )
    elif args.command == "digest":
        window = _window_from_args(args, config)
        _digest(
            config,
            window=window,
            language=args.language,
            digest_date=_digest_date_from_args(args, window, config),
        )
    elif args.command == "send-digest":
        window = _window_from_args(args, config)
        _send_digest(
            config,
            window=window,
            language=args.language,
            digest_date=_digest_date_from_args(args, window, config),
        )
    elif args.command == "daily":
        window = _window_from_args(args, config)
        _process(config, window=window, limit=args.limit, dry_run=False, force=args.force)
        _send_digest(
            config,
            window=window,
            language=args.language,
            digest_date=_digest_date_from_args(args, window, config),
        )
    else:
        raise ValueError(f"Unknown command: {args.command}")


def _fetch_test(config: AppConfig, *, limit: int) -> None:
    since = datetime.now(timezone.utc) - timedelta(days=3650)
    with mail_provider(config) as provider:
        emails = provider.fetch_recent_emails(since=since, target_email=config.target_email, limit=limit)

    print(f"Fetched {len(emails)} email(s) for {config.target_email} via {config.mail_provider}")
    for email in emails:
        created = email.created_at.isoformat() if email.created_at else "unknown"
        parsed = parse_email(email)
        attachment_image_count = sum(1 for item in email.attachments if is_supported_image_attachment(item))
        print(
            f"- {created} | {email.sender} | {email.subject} | {email.id} "
            f"| attachments={len(email.attachments)} attachment_images={attachment_image_count} "
            f"html_images={len(parsed.html_images)}"
        )


def _process(
    config: AppConfig,
    *,
    window: tuple[datetime, datetime | None],
    limit: int | None,
    dry_run: bool,
    force: bool = False,
) -> None:
    config.require_llm()
    since, until = window

    processed = 0
    skipped = 0
    filtered = 0
    analyses = []

    with (
        mail_provider(config) as provider,
        N1NLLMProvider(
            config.n1n_api_key,
            config.llm_model,
            base_url=config.n1n_base_url,
        ) as llm,
        EmailDatabase(config.database_url) as db,
    ):
        db.initialize()
        analyzer = EmailAnalyzer(llm)
        emails = provider.fetch_recent_emails(since=since, target_email=config.target_email, limit=limit)

        for email in emails:
            if until and email.created_at and email.created_at >= until:
                filtered += 1
                continue
            parsed = parse_email(email)
            if not is_allowed_sender(
                email,
                config.allowed_sender_domains,
                clean_text=parsed.clean_text,
            ):
                filtered += 1
                continue
            if force:
                db.delete_analysis(email.id)
            elif db.is_processed(email.id):
                skipped += 1
                continue

            images = []
            if config.enable_image_analysis:
                images = load_images_for_llm(
                    email=email,
                    provider=provider,
                    max_images=config.max_image_attachments,
                    max_bytes=config.max_image_bytes,
                    html_images=parsed.html_images,
                    include_remote_urls=config.enable_remote_image_urls,
                )
            analysis = replace(
                analyzer.analyze(parsed, images=images),
                subject=clean_forwarded_subject(email.subject),
            )
            analyses.append(analysis)

            if not dry_run:
                db.save_email_analysis(
                    email=email,
                    clean_text=parsed.clean_text,
                    analysis=analysis,
                    html_images=parsed.html_images,
                )
            processed += 1

    print(
        f"Processed {processed} email(s); skipped {skipped} already processed email(s); "
        f"filtered {filtered} sender(s)."
    )
    if analyses:
        if dry_run:
            print(json.dumps([item.to_dict() for item in analyses], ensure_ascii=False, indent=2))
        else:
            print()
            print(build_daily_digest_zh(analyses))


def _digest(
    config: AppConfig,
    *,
    window: tuple[datetime, datetime | None],
    language: str,
    digest_date,
) -> None:
    analyses = _load_analyses_for_window(config, window=window)
    print(_build_digest(analyses, language=language, digest_date=digest_date))


def _load_analyses_for_window(
    config: AppConfig,
    *,
    window: tuple[datetime, datetime | None],
):
    start, end = window
    with EmailDatabase(config.database_url) as db:
        db.initialize()
        if end is None:
            return db.list_recent_analyses(since=start)
        return db.list_analyses_between(start=start, end=end)


def _send_digest(
    config: AppConfig,
    *,
    window: tuple[datetime, datetime | None],
    language: str,
    digest_date,
) -> None:
    if config.mail_provider != "gmail":
        raise ValueError("send-digest currently uses Gmail API. Set MAIL_PROVIDER=gmail.")
    config.require_gmail()
    config.require_digest_email()

    analyses = _load_analyses_for_window(config, window=window)
    digest = _build_digest(analyses, language=language, digest_date=digest_date)
    subject = f"{config.digest_subject_prefix} - {digest_date.strftime('%Y-%m-%d')}"
    with gmail_provider(config) as gmail:
        sent = gmail.send_email(
            sender=config.digest_from_email,
            recipient=config.digest_recipient_email,
            subject=subject,
            text=digest,
            html=_digest_html(digest),
        )
    print(f"Sent digest to {config.digest_recipient_email}: {sent.get('id', 'unknown-id')}")


def _build_digest(analyses, *, language: str, digest_date=None) -> str:
    if language == "zh":
        return build_daily_digest_zh(analyses, digest_date=digest_date)
    return build_daily_digest(analyses)


@contextmanager
def mail_provider(config: AppConfig) -> Iterator[object]:
    if config.mail_provider == "gmail":
        with gmail_provider(config) as provider:
            yield provider
    elif config.mail_provider == "resend":
        config.require_resend()
        with ResendProvider(config.resend_api_key) as provider:
            yield provider
    else:
        raise ValueError("MAIL_PROVIDER must be either 'gmail' or 'resend'.")


@contextmanager
def gmail_provider(config: AppConfig) -> Iterator[GmailProvider]:
    config.require_gmail()
    with GmailProvider(
        client_secrets_file=config.google_oauth_client_secrets,
        token_file=config.google_oauth_token_file,
        user_id=config.gmail_user,
        expected_account_email=config.gmail_account_email or None,
    ) as provider:
        yield provider


def _digest_html(digest: str) -> str:
    escaped = (
        digest.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )
    return f"<div style=\"font-family:Arial,sans-serif;line-height:1.5\">{escaped}</div>"


def _since_from_args(args: argparse.Namespace, config: AppConfig) -> datetime:
    return _window_from_args(args, config)[0]


def _window_from_args(args: argparse.Namespace, config: AppConfig) -> tuple[datetime, datetime | None]:
    local_zone = ZoneInfo(config.local_timezone)
    if getattr(args, "date", None):
        start_local = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=local_zone)
        end_local = start_local + timedelta(days=1)
        return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)
    if getattr(args, "yesterday", False):
        today = datetime.now(local_zone).replace(hour=0, minute=0, second=0, microsecond=0)
        start_local = today - timedelta(days=1)
        return start_local.astimezone(timezone.utc), today.astimezone(timezone.utc)
    if getattr(args, "today", False):
        now = datetime.now(local_zone)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
        return start, None
    return datetime.now(timezone.utc) - timedelta(hours=args.hours), None


def _digest_date_from_args(args: argparse.Namespace, window: tuple[datetime, datetime | None], config: AppConfig):
    if getattr(args, "digest_date", None):
        return datetime.strptime(args.digest_date, "%Y-%m-%d").date()
    if getattr(args, "yesterday", False):
        return datetime.now(ZoneInfo(config.local_timezone)).date()

    start, end = window
    local_zone = ZoneInfo(config.local_timezone)
    if end is not None:
        return start.astimezone(local_zone).date()
    return datetime.now(local_zone).date()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PolyU Student Email Assistant")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_test = subparsers.add_parser("fetch-test", help="Read recent inbound emails.")
    fetch_test.add_argument("--limit", type=int, default=10)

    process = subparsers.add_parser("process", help="Process recent emails through the LLM.")
    process.add_argument("--hours", type=int, default=24)
    process.add_argument("--today", action="store_true")
    process.add_argument("--yesterday", action="store_true")
    process.add_argument("--date")
    process.add_argument("--limit", type=int, default=None)
    process.add_argument("--dry-run", action="store_true")
    process.add_argument("--force", action="store_true")

    digest = subparsers.add_parser("digest", help="Build digest from saved analyses.")
    digest.add_argument("--hours", type=int, default=24)
    digest.add_argument("--today", action="store_true")
    digest.add_argument("--yesterday", action="store_true")
    digest.add_argument("--date")
    digest.add_argument("--digest-date")
    digest.add_argument("--language", choices=["en", "zh"], default="zh")

    send_digest = subparsers.add_parser("send-digest", help="Email digest from saved analyses.")
    send_digest.add_argument("--hours", type=int, default=24)
    send_digest.add_argument("--today", action="store_true")
    send_digest.add_argument("--yesterday", action="store_true")
    send_digest.add_argument("--date")
    send_digest.add_argument("--digest-date")
    send_digest.add_argument("--language", choices=["en", "zh"], default="zh")

    daily = subparsers.add_parser("daily", help="Process recent emails and email the digest.")
    daily.add_argument("--hours", type=int, default=24)
    daily.add_argument("--today", action="store_true")
    daily.add_argument("--yesterday", action="store_true")
    daily.add_argument("--date")
    daily.add_argument("--digest-date")
    daily.add_argument("--limit", type=int, default=None)
    daily.add_argument("--language", choices=["en", "zh"], default="zh")
    daily.add_argument("--force", action="store_true")

    return parser.parse_args()


if __name__ == "__main__":
    main()
