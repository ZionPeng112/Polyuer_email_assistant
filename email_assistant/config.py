from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


DEFAULT_TARGET_EMAIL = "polyu@faloukulee.resend.app"
DEFAULT_N1N_BASE_URL = "https://api.n1n.ai/v1"
DEFAULT_DATABASE_URL = "sqlite:///data/emails.db"
DEFAULT_GOOGLE_OAUTH_CLIENT_SECRETS = "credentials/google_oauth_client.json"
DEFAULT_GOOGLE_OAUTH_TOKEN_FILE = "data/google_token.json"
DEFAULT_DIGEST_SUBJECT_PREFIX = "PolyU Daily Email Digest"
DEFAULT_LOCAL_TIMEZONE = "Asia/Shanghai"


@dataclass(frozen=True)
class AppConfig:
    mail_provider: str
    resend_api_key: str
    gmail_user: str
    gmail_account_email: str
    google_oauth_client_secrets: str
    google_oauth_token_file: str
    target_email: str
    allowed_sender_domains: list[str]
    local_timezone: str
    n1n_api_key: str
    n1n_base_url: str
    llm_model: str
    n1n_timeout_seconds: int
    database_url: str
    digest_recipient_email: str
    digest_from_email: str
    digest_subject_prefix: str
    enable_image_analysis: bool
    enable_remote_image_urls: bool
    max_image_attachments: int
    max_image_bytes: int

    @classmethod
    def from_env(cls, env_file: str | Path | None = ".env") -> "AppConfig":
        if env_file:
            load_dotenv(env_file)

        return cls(
            mail_provider=os.getenv("MAIL_PROVIDER", "gmail").strip().lower(),
            resend_api_key=os.getenv("RESEND_API_KEY", "").strip(),
            target_email=os.getenv("TARGET_EMAIL", DEFAULT_TARGET_EMAIL).strip().lower(),
            allowed_sender_domains=_env_list("ALLOWED_SENDER_DOMAINS"),
            local_timezone=os.getenv("LOCAL_TIMEZONE", DEFAULT_LOCAL_TIMEZONE).strip()
            or DEFAULT_LOCAL_TIMEZONE,
            gmail_user=os.getenv("GMAIL_USER", "me").strip() or "me",
            gmail_account_email=os.getenv("GMAIL_ACCOUNT_EMAIL", "").strip().lower(),
            google_oauth_client_secrets=os.getenv(
                "GOOGLE_OAUTH_CLIENT_SECRETS",
                DEFAULT_GOOGLE_OAUTH_CLIENT_SECRETS,
            ).strip(),
            google_oauth_token_file=os.getenv(
                "GOOGLE_OAUTH_TOKEN_FILE",
                DEFAULT_GOOGLE_OAUTH_TOKEN_FILE,
            ).strip(),
            n1n_api_key=os.getenv("N1N_API_KEY", "").strip(),
            n1n_base_url=os.getenv("N1N_BASE_URL", DEFAULT_N1N_BASE_URL).rstrip("/"),
            llm_model=os.getenv("LLM_MODEL", "").strip(),
            n1n_timeout_seconds=_env_int("N1N_TIMEOUT_SECONDS", default=180),
            database_url=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL).strip(),
            digest_recipient_email=os.getenv("DIGEST_RECIPIENT_EMAIL", "").strip(),
            digest_from_email=os.getenv("DIGEST_FROM_EMAIL", "").strip(),
            digest_subject_prefix=os.getenv(
                "DIGEST_SUBJECT_PREFIX",
                DEFAULT_DIGEST_SUBJECT_PREFIX,
            ).strip(),
            enable_image_analysis=_env_bool("ENABLE_IMAGE_ANALYSIS", default=True),
            enable_remote_image_urls=_env_bool("ENABLE_REMOTE_IMAGE_URLS", default=True),
            max_image_attachments=_env_int("MAX_IMAGE_ATTACHMENTS", default=4),
            max_image_bytes=_env_int("MAX_IMAGE_BYTES", default=2_000_000),
        )

    def require_resend(self) -> None:
        if not self.resend_api_key:
            raise ValueError("RESEND_API_KEY is required.")

    def require_gmail(self) -> None:
        missing = [
            name
            for name, value in (
                ("GOOGLE_OAUTH_CLIENT_SECRETS", self.google_oauth_client_secrets),
                ("GOOGLE_OAUTH_TOKEN_FILE", self.google_oauth_token_file),
                ("TARGET_EMAIL", self.target_email),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"Missing required Gmail configuration: {', '.join(missing)}")

        if not Path(self.google_oauth_client_secrets).exists():
            raise FileNotFoundError(
                "Google OAuth client file is missing: "
                f"{self.google_oauth_client_secrets}. Create an OAuth client in Google Cloud "
                "Console and save the downloaded JSON at this path."
            )

    def require_digest_email(self) -> None:
        missing = [
            name
            for name, value in (
                ("DIGEST_RECIPIENT_EMAIL", self.digest_recipient_email),
                ("DIGEST_FROM_EMAIL", self.digest_from_email),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"Missing digest email configuration: {', '.join(missing)}")

    def require_llm(self) -> None:
        missing = [
            name
            for name, value in (
                ("N1N_API_KEY", self.n1n_api_key),
                ("LLM_MODEL", self.llm_model),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"Missing required LLM configuration: {', '.join(missing)}")


def sqlite_path_from_url(database_url: str) -> Path:
    if database_url.startswith("sqlite:///"):
        return Path(database_url.removeprefix("sqlite:///"))
    if database_url.startswith("sqlite://"):
        return Path(database_url.removeprefix("sqlite://"))
    raise ValueError("Only sqlite:/// DATABASE_URL values are supported in the MVP.")


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, *, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _env_list(name: str) -> list[str]:
    value = os.getenv(name, "")
    return [item.strip().lower() for item in value.split(",") if item.strip()]
