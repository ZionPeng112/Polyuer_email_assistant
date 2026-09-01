# PolyU Student Email Assistant

Student Email Intelligence Assistant for PolyU forwarded email.

The MVP flow is:

```text
PolyU -> Gmail -> Gmail API -> Parser -> n1n LLM -> SQLite -> Daily Digest -> Gmail API
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill `.env` with your Gmail OAuth paths and n1n credentials.

## Gmail OAuth

Gmail is now the default mail provider:

```env
MAIL_PROVIDER=gmail
GMAIL_USER=me
GMAIL_ACCOUNT_EMAIL=zionpeng112@gmail.com
TARGET_EMAIL=zionpeng112@gmail.com
GOOGLE_OAUTH_CLIENT_SECRETS=credentials/google_oauth_client.json
GOOGLE_OAUTH_TOKEN_FILE=data/google_token.json
DIGEST_RECIPIENT_EMAIL=zionpeng112@gmail.com
DIGEST_FROM_EMAIL=zionpeng112@gmail.com
```

To authorize Gmail:

1. Open Google Cloud Console and create or select a project.
2. Enable the Gmail API.
3. Configure OAuth consent for a desktop/testing app.
4. Create an OAuth Client ID with application type `Desktop app`.
5. Download the JSON credentials and place them at:

```text
credentials/google_oauth_client.json
```

6. Run a Gmail command locally:

```bash
python -m email_assistant.main fetch-test --limit 5
```

The first run opens a browser OAuth consent flow. After success, the refresh token is saved at
`data/google_token.json`, which is ignored by Git.

The app requests these Gmail scopes:

```text
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/gmail.send
```

Image analysis is enabled by default through:

```env
ENABLE_IMAGE_ANALYSIS=true
ENABLE_REMOTE_IMAGE_URLS=true
MAX_IMAGE_ATTACHMENTS=4
MAX_IMAGE_BYTES=2000000
```

The app downloads supported image attachments only during processing, sends bounded data URLs to
the LLM, and stores only attachment metadata plus body hash in SQLite. HTML email images that are
remote URLs are parsed separately and can be sent to a vision-capable model when
`ENABLE_REMOTE_IMAGE_URLS=true`. It does not persist image files by default.

## Commands

Read recent inbound emails without calling the LLM:

```bash
python -m email_assistant.main fetch-test --limit 10
```

Process the last 24 hours:

```bash
python -m email_assistant.main process --hours 24
```

Preview processing without writing to SQLite:

```bash
python -m email_assistant.main process --hours 24 --dry-run
```

Generate a digest from saved analyses:

```bash
python -m email_assistant.main digest --hours 24
```

Email the digest from saved analyses:

```bash
python -m email_assistant.main send-digest --hours 24
```

Process recent emails and email the digest:

```bash
python -m email_assistant.main daily --hours 24
```

## GitHub Actions

The repository includes a scheduled workflow:

```text
.github/workflows/daily-digest.yml
```

It starts a temporary Linux runner every day at 11:40 Asia/Shanghai. It installs Python
dependencies, restores Gmail OAuth from GitHub Secrets, runs tests, and sends the Daily Digest with:

```bash
python -m email_assistant.main daily --yesterday
```

See [docs/github-actions.md](docs/github-actions.md) for the required secrets and setup commands.

## Module Boundaries

- `providers/gmail.py`: Gmail OAuth, message read, attachment read, and digest sending.
- `providers/resend.py`: Resend inbound API fallback only. No AI logic.
- `parser.py`: HTML/text cleanup only. No classification.
- `providers/n1n.py`: n1n OpenAI-compatible chat API only.
- `analyzer.py`: prompt construction, schema validation, fallback normalization.
- `database.py`: SQLite persistence and deduplication.
- `digest.py`: digest formatting from saved `EmailAnalysis` records.

## Categories

- `MUST_ACTION`: the student must complete an action.
- `MUST_ATTEND`: attendance is explicitly compulsory or required.
- `ACADEMIC_NOTICE`: important academic notice without a required action.
- `OPTIONAL_EVENT`: invited/recommended events without mandatory wording.
- `GENERAL`: ordinary notices, newsletters, promotions, FYI messages.

Important rule: "You are invited to attend" is optional unless the email also contains clear wording such as "Attendance is compulsory" or "You are required to attend".
