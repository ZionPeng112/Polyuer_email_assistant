# GitHub Actions Deployment

The daily workflow is defined in:

```text
.github/workflows/daily-digest.yml
```

It runs every day at 09:30 Asia/Shanghai and can also be started manually from the
GitHub Actions tab.

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
