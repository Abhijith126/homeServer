# qbittorrent

> Torrent client behind a **gluetun VPN killswitch** — runs on the **storage** node (ryzen) · category: `downloads`

`qbittorrent` uses `network_mode: service:gluetun`, so every packet exits through the VPN. If gluetun's tunnel drops, qBittorrent has no network — no leaks.

## Access

|       |                        |
| ----- | ---------------------- |
| URL   | `https://qbit.${DOMAIN}` |
| Local | `http://ryzen:${QBIT_PORT}` |
| Node  | `storage` (ryzen)      |

## Configuration

Every VPN variable in `.env` is passed straight to gluetun (via `env_file`), so the stack works with **either OpenVPN or WireGuard** — just set `VPN_TYPE`. VPN credentials are set centrally in the root `.env` + `make config` (see [conventions](../../../docs/conventions.md)).

| Variable                              | Description                                          |
| ------------------------------------- | --------------------------------------------------- |
| `VPN_SERVICE_PROVIDER`                | e.g. `mullvad`, `protonvpn`, `fastestvpn`, `custom` |
| `VPN_TYPE`                            | `openvpn` or `wireguard`                            |
| `OPENVPN_USER` / `OPENVPN_PASSWORD`   | for OpenVPN providers                               |
| `WIREGUARD_PRIVATE_KEY` / `WIREGUARD_ADDRESSES` | for WireGuard providers                   |
| `SERVER_COUNTRIES`                    | preferred exit country                              |
| `LAN_NETWORK`                         | your LAN CIDR (keeps the WebUI reachable)           |
| `QBIT_PORT`                           | WebUI host port                                     |

> Provider var reference: the [gluetun wiki](https://github.com/qdm12/gluetun-wiki).

```bash
cp .env.example .env && $EDITOR .env
docker compose up -d
```

## First run

LSIO sets a **temporary WebUI password** — read it from the logs, then change it in the UI:

```bash
docker compose logs qbittorrent | grep -i password
```

Behind the reverse proxy, set **Options → Web UI → "Bypass authentication"** off and enable **"Enable Host header validation"** exceptions if you see `Unauthorized`.

## Verify the VPN

```bash
docker compose exec gluetun wget -qO- https://ipinfo.io/ip   # should show the VPN's IP, not yours
```

## Volumes

| Path                          | Purpose            | Backed up          |
| ----------------------------- | ------------------ | ------------------ |
| `${DOCKER_DATA}/qbittorrent`  | Config             | yes → `backup.sh`  |
| `${MEDIA_ROOT}/Downloads`     | Downloads          | it's the data      |

## Links

- gluetun: https://github.com/qdm12/gluetun · qBittorrent (LSIO): https://docs.linuxserver.io/images/docker-qbittorrent
