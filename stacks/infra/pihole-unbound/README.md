# pihole-unbound

> Network-wide ad-blocking DNS + recursive Unbound resolver — runs on the **infra** node · category: `dns`

Uses the combined `cbcrowe/pihole-unbound` image (pinned), preserving your current setup: DNSSEC validation in Unbound, Unbound as the upstream (`127.0.0.1#5335`), and conditional forwarding to the router for `.local` names.

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
| `${DOCKER_DATA}/pihole-unbound/etc-dnsmasq` | dnsmasq config | yes → `backup.sh` |
| `unbound-state` (named volume) | Unbound root trust anchors | retained across recreation; recoverable from signed IANA data |

## Links

- Image: https://github.com/chriscrowe/docker-pihole-unbound · Adlists: https://firebog.net

## DNSSEC trust-anchor recovery

The legacy Pi-hole v5 image has its own DNSSEC validation, independent of Unbound. Keep Pi-hole's Use DNSSEC checkbox off and its upstream at 127.0.0.1#5335; DNSSEC validation remains enabled in Unbound. The October 2026 root-key rollover exposed both an ADDPEND Unbound anchor and a failing second validation pass in Pi-hole.

The s6 Unbound startup script refreshes the root anchor through unbound-anchor's forced, signature-verified IANA XML recovery path before starting the daemon. Never refresh the active anchor while Unbound is running: it may overwrite the file with in-memory state. Unbound state is persisted in a named volume so it survives container recreation. A fresh volume is bootstrapped from verified anchor data. The refresh requires outbound DNS and HTTPS; failed refreshes retain existing anchor data, and the healthcheck checks whether DNS actually works.

Health checks require an authenticated (AD) root DNSKEY response from Unbound and a NOERROR root NS response through Pi-hole. dig's exit status alone is insufficient because it can exit successfully for SERVFAIL responses. These checks depend on working outbound DNS; the container may be marked unhealthy during an outage. Allow startup time for rebuilding large blocklists. Do not run compose down -v, which deletes the named anchor volume.

For an immediate correction before this change is deployed, open the Pi-hole UI at http://<infra-ip>:<web-port>/admin, go to Settings > DNS, uncheck Use DNSSEC, and save. After DNS is restored, the existing infra updater can pull and deploy this change. Do not attempt a Pi-hole v5-to-v6 migration as part of incident recovery; this patch keeps the pinned image and existing Pi-hole data.
