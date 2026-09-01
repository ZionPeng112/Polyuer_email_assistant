# GitHub Actions Deployment

The daily workflow is defined in:

```text
.github/workflows/daily-digest.yml
```

GitHub's built-in `schedule` event is not used because it did not reliably dispatch runs for
this repository. The workflow is triggered with `workflow_dispatch`, either manually from the
GitHub Actions tab or by an external cron service.

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

Workflow logs only report processing and delivery status. They do not print the digest body,
evidence fields, or "判断依据" content.

## External Cron

Configure an external cron service to call GitHub's workflow dispatch endpoint every day at
11:40 Asia/Hong_Kong.

If the cron service supports time zones, use:

```text
40 11 * * *
```

with time zone:

```text
Asia/Hong_Kong
```

If it only supports UTC, use:

```text
40 3 * * *
```

Create a fine-grained GitHub personal access token for this repository with:

```text
Actions: Read and write
```

The external cron job should make this HTTP request:

```bash
curl -L \
  -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/ZionPeng112/email_assist/actions/workflows/daily-digest.yml/dispatches \
  -d '{"ref":"main"}'
```

Do not store the token in this repository.

## Daily Command

The dispatched workflow runs:

```bash
python -m email_assistant.main daily --yesterday
```

Because `--yesterday` uses `LOCAL_TIMEZONE=Asia/Hong_Kong`, the workflow covers the full previous
local day, from 00:00 through 24:00 Asia/Hong_Kong. The digest itself is dated on the send day, so
events happening that morning/day are still shown under "今天的活动".

Before sending, the app checks Gmail Sent mail for the same recipient and digest subject. To
override this for a manual resend, run `send-digest` or `daily` with `--force-send`.
