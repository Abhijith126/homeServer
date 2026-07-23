# diun

> Docker Image Update Notifier — replaces Watchtower · category: `updates`

**Notify-only:** emails you when a newer image is published for a watched container, but never auto-pulls. This matches the platform's pinned-version model — you review release notes and bump tags in git deliberately.

**Deploy on every node** (like a DaemonSet) so each host's containers are watched. Diun only watches containers labelled `diun.enable=true` (already set across all stacks).

## Setup (per node)

```bash
cp .env.example .env && $EDITOR .env      # fill in your Brevo SMTP creds
docker compose up -d
```

## Configuration

| Variable              | Description                          | Example                |
| --------------------- | ------------------------------------ | ---------------------- |
| `DIUN_WATCH_SCHEDULE` | Cron for checks (in `compose.yaml`)  | `0 */6 * * *`          |
| `SMTP_HOST`/`SMTP_PORT` | Mail relay                         | `smtp-relay.brevo.com` / `587` |
| `SMTP_USERNAME`/`SMTP_PASSWORD` | SMTP creds (**secret**)    | —                      |
| `MAIL_FROM`/`MAIL_TO` | Notification addresses               | —                      |

## Why not Watchtower?

Watchtower auto-updates, which fights version pinning (and would be inert against fixed tags anyway). Diun keeps you informed while git stays the source of truth. Other notifiers (Slack, Telegram, Discord, Gotify) are a one-line env swap — see the docs.

## Links

- Upstream: https://crazymax.dev/diun/
