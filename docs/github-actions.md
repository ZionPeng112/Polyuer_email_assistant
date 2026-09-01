# GitHub Actions Deployment

The daily workflow is defined in:

```text
.github/workflows/daily-digest.yml
```

It runs every day at 09:30 Asia/Shanghai, with a 09:45 backup schedule in case GitHub
drops or delays the first scheduled event. It can also be started manually from the GitHub
Actions tab.

The cloud workflow keeps image analysis enabled:

```text
ENABLE_REMOTE_IMAGE_URLS=true
```

HTML image URLs are downloaded by the Email Assistant first and sent to the LLM as bounded
`data:image/...;base64` payloads. This avoids asking the LLM gateway to fetch remote image URLs
itself.

## Required Secrets

Set these GitHub repository secrets:

```text
GOOGLE_OAUTH_CLIENT_JSON_B64
GOOGLE_OAUTH_TOKEN_JSON_B64
N1N_API_KEY
```

Create the base64 values locally:

```bash
base64 -i credentials/google_oauth_client.json | pbcopy
base64 -i data/google_token.json | pbcopy
```

Then add them to GitHub:

```bash
gh secret set GOOGLE_OAUTH_CLIENT_JSON_B64 --body '<base64 value>'
gh secret set GOOGLE_OAUTH_TOKEN_JSON_B64 --body '<base64 value>'
gh secret set N1N_API_KEY --body '<n1n api key>'
```

Or run the helper after authenticating `gh`:

```bash
bash scripts/setup-github-secrets.sh
```

The workflow creates these files only inside the temporary GitHub runner:

```text
credentials/google_oauth_client.json
data/google_token.json
data/emails.db
```

They are not committed to the repository.

## Daily Command

The scheduled job runs:

```bash
python -m email_assistant.main daily --yesterday
```

Because `--yesterday` uses `LOCAL_TIMEZONE=Asia/Shanghai`, the workflow covers the full previous
local day, from 00:00 through 24:00 Asia/Shanghai. The digest itself is dated on the send day, so
events happening that morning/day are still shown under "今天的活动".

Before sending, the app checks Gmail Sent mail for the same recipient and digest subject. If the
09:30 run already sent the digest, the 09:45 backup run exits without sending a duplicate. To
override this for a manual resend, run `send-digest` or `daily` with `--force-send`.
