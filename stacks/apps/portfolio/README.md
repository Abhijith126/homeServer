# portfolio

> Personal website — runs on the **apps** node · category: `web`

Unlike the other stacks, this runs a **locally-built image** from your own portfolio repository — this repo only orchestrates it.

## Access

|       |                           |
| ----- | ------------------------- |
| URL   | `https://portfolio.${DOMAIN}` |
| Local | `http://apps:${PORTFOLIO_PORT}` |
| Node  | `apps`                    |

## Build & deploy

```bash
# in your portfolio repo
docker build -t ghcr.io/<you>/portfolio:1.0.0 .
docker push  ghcr.io/<you>/portfolio:1.0.0

# here
cp .env.example .env       # set PORTFOLIO_IMAGE to the tag you pushed
$EDITOR .env
docker compose up -d
```

`diun.enable` is `false` because there's no upstream registry image to watch — you bump the tag yourself when you rebuild.

## Notes

Stateless — no volumes, no `backup.sh`. If you later add a build pipeline, you could add a `build:` section pointing at the portfolio repo instead of a pre-built image.
