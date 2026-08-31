# GitHub Actions Deployment

The daily workflow is defined in:

```text
.github/workflows/daily-digest.yml
```

It runs every day at 23:55 Asia/Shanghai and can also be started manually from the
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
python -m email_assistant.main daily --today
```

Because `--today` uses `LOCAL_TIMEZONE=Asia/Shanghai`, the workflow is scheduled near the
end of the local day so the digest covers that day's forwarded PolyU email.
