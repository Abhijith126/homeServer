# Hardware

## Nodes

| Node | Hostname | CPU | RAM | Disks | OS | Role |
| --- | --- | --- | --- | --- | --- | --- |
| storage | `ryzen` | Ryzen 3 2200G | 16 GB | 256 GB SSD (boot) · 2×4 TB HDD (RAID) | Ubuntu Server | Storage + media |
| apps | `apps` | i7-5500U | 16 GB | 32 GB SSD | Debian 13 | Applications |
| infra | `infra` | Celeron 3865U | 8 GB | 16 GB SSD | Debian 13 | Edge / infra |

## Storage layout (ryzen)

| Path | Backing | Purpose |
| --- | --- | --- |
| `/` | 256 GB SSD | OS + Docker |
| `/mnt/nas` | 2×4 TB RAID | Media & data (`Movies`, `Shows`, `Music`, `Downloads`, `Gallery`, `Files`) — exported via NFS |
| `/mnt/hdd2` | HDD | Backup target (Duplicati + per-stack `backup.sh`) |
| `/opt/homelab/data` | SSD | Per-app config bind mounts |

App/infra nodes mount `ryzen:/mnt/nas → /mnt/nas` and `ryzen:/mnt/hdd2 → /mnt/nfs/backup`.

## Sizing notes

- The **infra** node is intentionally low-power — DNS, proxy, and Beszel are light. This is why monitoring is Beszel (tiny) rather than Prometheus/Grafana.
- The **apps** node has the most RAM headroom for the *arr suite + Home Assistant.
- **ryzen**'s Vega iGPU supports VAAPI for Jellyfin hardware transcoding (opt-in — see the jellyfin stack).

## Recommendations for new hardware

- Boot on SSD; keep bulk data on dedicated HDDs in RAID (mirror for redundancy).
- Keep the backup disk **separate** from the RAID array (a failed array shouldn't take backups with it).
- 8 GB RAM is enough for an edge node; 16 GB+ for the app node if you run many services.
- Any x86-64 box running Debian/Ubuntu works — the Ansible bootstrap is hardware-agnostic.
