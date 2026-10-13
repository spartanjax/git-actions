# git-actions

Pushes a daily ntfy notification with today's Mt Eden (Maungawhau) sunset and
tomorrow's sunrise.

Example message:

> 🌅 Sunset today: 7:34pm · 🌄 Sunrise tomorrow: 6:12am

## How it works

```
cron-job.org (17:00 Pacific/Auckland, DST-aware)
        │  POST /repos/spartanjax/git-actions/dispatches
        ▼
GitHub Actions workflow (.github/workflows/sunrise-sunset.yml)
        │  runs scripts/sunset_notify.py
        ▼
ntfy.sh topic: mt-eden-sunsets
```

The timing is owned by **cron-job.org**, not by GitHub's `on: schedule` trigger.
GitHub's scheduler never fired for this repo (0 scheduled runs, ever), so the
workflow is triggered by a `repository_dispatch` event (`sunset-notify`) that
cron-job.org sends once a day.

## External scheduler setup (cron-job.org)

- **URL:** `https://api.github.com/repos/spartanjax/git-actions/dispatches`
- **Method:** `POST`
- **Schedule:** daily at `17:00`, timezone `Pacific/Auckland` (DST handled by cron-job.org)
- **Headers:**
  - `Authorization: Bearer <FINE_GRAINED_PAT>`
  - `Accept: application/vnd.github+json`
  - `X-GitHub-Api-Version: 2026-03-10`
  - `Content-Type: application/json`
- **Body:** `{"event_type":"sunset-notify"}`
- Failure notifications are enabled so an expired/revoked token surfaces quickly.

### PAT

A **fine-grained** personal access token scoped to **only** `spartanjax/git-actions`:

- Repository permission: **Contents → Read and write** (required for `repository_dispatch`).
- The token is stored in cron-job.org, so give it an expiry and **rotate it** before
  it lapses (otherwise notifications silently stop).

## Manual run

Trigger by hand from the CLI or the Actions tab:

```bash
gh workflow run "Mt Eden Sun Times" -R spartanjax/git-actions
```

or via the API:

```bash
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GH_TOKEN" \
  https://api.github.com/repos/spartanjax/git-actions/actions/workflows/sunrise-sunset.yml/dispatches \
  -d '{"ref":"main"}'
```
