# pihole-unbound

> Network-wide ad-blocking DNS + recursive Unbound resolver — runs on the **infra** node · category: `dns`

Uses the combined `cbcrowe/pihole-unbound` image (pinned), preserving your current setup: DNSSEC on, Unbound as the upstream (`127.0.0.1#5335`), and conditional forwarding to the router for `.local` names.

## Access

|       |                          |
| ----- | ------------------------ |
| URL   | `https://pihole.${DOMAIN}/admin` |
| Local | `http://infra:${PIHOLE_WEB_PORT}/admin` |
| DNS   | `${PIHOLE_HOST_IP}:53`   |
| Node  | `infra`                  |

## Configuration

| Variable            | Description                                | Example          |
| ------------------- | ------------------------------------------ | ---------------- |
| `PIHOLE_HOST_IP`    | Infra node LAN IP (clients' DNS target)    | `192.168.1.120`  |
| `PIHOLE_WEB_PORT`   | Web UI host port (Caddy fronts it)         | `8081`           |
| `PIHOLE_WEBPASSWORD`| Admin password (**change it**)             | —                |
| `ROUTER_IP`         | Conditional-forwarding target              | `192.168.1.1`    |

```bash
cp .env.example .env && $EDITOR .env
docker compose up -d
```

> **Host prerequisite:** on Debian/Ubuntu, `systemd-resolved` binds port 53. Free it before starting (the Ansible `common` role handles this):
> ```bash
> sudo sed -i 's/#DNSStubListener=yes/DNSStubListener=no/' /etc/systemd/resolved.conf
> sudo systemctl restart systemd-resolved
> ```
> Then point your router's DHCP DNS at `${PIHOLE_HOST_IP}`.

## Volumes

| Path                                      | Purpose               | Backed up          |
| ----------------------------------------- | --------------------- | ------------------ |
| `${DOCKER_DATA}/pihole-unbound/etc-pihole`  | Adlists, config, stats | yes → `backup.sh` |
| `${DOCKER_DATA}/pihole-unbound/etc-dnsmasq` | dnsmasq/unbound config | yes → `backup.sh` |

## Links

- Image: https://github.com/chriscrowe/docker-pihole-unbound · Adlists: https://firebog.net
