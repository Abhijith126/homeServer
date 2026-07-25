# homeassistant

> Home automation — runs on the **apps** node · category: `home-automation`

Runs with `network_mode: host` (device/mDNS discovery) and `privileged: true` (USB Zigbee/Z-Wave/Bluetooth radios), matching the current deployment.

## Access

|       |                        |
| ----- | ---------------------- |
| URL   | `https://home.${DOMAIN}` |
| Local | `http://apps:8123`     |
| Node  | `apps`                 |

## Configuration

| Variable      | Description                       | Example    |
| ------------- | --------------------------------- | ---------- |
| `DOCKER_DATA` | Holds HA's `/config`              | `/opt/homelab/data` |
| `MEDIA_ROOT`  | NAS mount exposed at `/media`     | `/mnt/nas` |

```bash
cp .env.example .env && $EDITOR .env
docker compose up -d
```

> **Reverse proxy:** add these to `configuration.yaml` so HA trusts Caddy:
> ```yaml
> http:
>   use_x_forwarded_for: true
>   trusted_proxies:
>     - <infra-node-ip>
> ```
>
> If you have no USB radios, you can drop `privileged: true` and pass specific `devices:` instead.

## Volumes

| Path                           | Purpose | Backed up          |
| ------------------------------ | ------- | ------------------ |
| `${DOCKER_DATA}/homeassistant` | Config  | yes → `backup.sh`  |

## Links

- Upstream: https://www.home-assistant.io
