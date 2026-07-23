# Disaster recovery

How to recover from a lost container, a dead node, or a total rebuild.

## What is backed up, and where

| Data | Location | Protected by |
| --- | --- | --- |
| App configs | `/opt/homelab/data/<app>` | per-stack `backup.sh` → `${NFS_BACKUP}` |
| Immich database | Postgres (on ryzen) | `stacks/storage/immich/backup.sh` (`pg_dumpall`) |
| Backup archives | `/mnt/hdd2` (ryzen) | Duplicati → off-site/versioned |
| Media & photos | `/mnt/nas` (RAID) | RAID mirror + Duplicati |
| Infrastructure as code | this git repo | git remote |

**Test restores periodically** — an untested backup is a hope, not a plan.

## Scenario 1 — A single stack is broken

```bash
cd stacks/<node>/<app>
docker compose down
./restore.sh              # newest config archive (or ./restore.sh <file>)
docker compose up -d
```

## Scenario 2 — A disk in the RAID fails

Replace the disk and let the array rebuild (mdadm/ZFS). Media stays available during rebuild. If the whole array is lost, recover media from Duplicati into a fresh `/mnt/nas`.

## Scenario 3 — Rebuild a node from zero

```mermaid
flowchart TB
    a["1. Install OS + SSH key"] --> b["2. Ansible provision<br/>(docker, nfs, tailscale, ufw)"]
    b --> c["3. Restore configs<br/>to /opt/homelab/data"]
    c --> d["4. Restore databases<br/>(immich, etc.)"]
    d --> e["5. docker compose up -d<br/>per stack"]
    e --> f["6. Re-point DNS + verify"]
```

### Step by step

1. **OS + access.** Install Debian/Ubuntu, enable SSH, copy your key, set the static IP in `inventory.ini`.
2. **Provision.**
   ```bash
   cd ansible && ansible-galaxy collection install -r requirements.yml
   ansible-playbook site.yml --limit <node> -e tailscale_authkey=tskey-...
   ```
   (Rebuild **ryzen first** so NFS is up before apps/infra mount it.)
3. **Restore configs.** For each stack on the node:
   ```bash
   cd stacks/<node>/<app>
   cp .env.example .env && $EDITOR .env     # restore secrets
   ./restore.sh                             # pulls newest config archive from ${NFS_BACKUP}
   ```
   If `${NFS_BACKUP}` itself is gone, restore it from Duplicati first.
4. **Restore databases.**
   - **Immich:** `cd stacks/storage/immich && ./restore.sh` (recreates the DB volume and loads the newest `pg_dumpall`). The photo library on `/mnt/nas/Gallery` is untouched.
5. **Deploy.** `docker compose up -d` in each stack (or re-add the Portainer Git stacks).
6. **Re-point the network.**
   - Router DHCP DNS → infra node IP (Pi-hole).
   - Confirm `ryzen`/`apps`/`infra` resolve (Tailscale MagicDNS).
   - Set `DOMAIN`/`ACME_EMAIL` in the Caddy stack; Caddy re-issues certificates automatically.

## Scenario 4 — Total loss (all nodes)

1. Clone this repo.
2. Rebuild **ryzen** (Scenario 3) — it holds the data and NFS exports.
3. Restore `/mnt/nas` (media) and `/mnt/hdd2` (backups) from Duplicati / off-site.
4. Rebuild **apps** and **infra**.
5. Restore each stack's config + databases, deploy, re-point DNS.

## Recovery verification checklist

- [ ] All containers `healthy` (`docker ps`)
- [ ] Immich loads and shows the library; a test upload works
- [ ] Jellyfin plays media
- [ ] *arr apps reach indexers (Prowlarr) and the download client
- [ ] DNS resolves + ad-blocking active (Pi-hole query log)
- [ ] Caddy serves each `app.${DOMAIN}` over HTTPS
- [ ] Beszel shows all nodes reporting
- [ ] A fresh `./backup.sh` succeeds on a couple of stacks

## Keep off-box

Store these somewhere **not** on the homelab (password manager / encrypted vault):

- Each stack's `.env` (or at least the secrets)
- Duplicati passphrase + `DUPLICATI_SETTINGS_ENCRYPTION_KEY`
- Immich `DB_PASSWORD`, Homarr `SECRET_ENCRYPTION_KEY`
- Tailscale auth keys, VPN (gluetun) credentials
