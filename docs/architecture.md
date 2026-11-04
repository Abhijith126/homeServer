# Architecture

Two physical servers: Ryzen provides storage and Lenovo runs Proxmox. There are only two Docker targets, `storage` and `docker`. Home Assistant is a separate VM on Lenovo, not a container.

```mermaid
flowchart LR
    clients[Clients] --> dns["Lenovo Docker VM .121: Pi-hole / Unbound"]
    clients --> caddy["Lenovo Docker VM .121: Caddy"]
    caddy --> applications[".121: dashboards, monitoring, media automation, Portainer"]
    caddy --> ha["Lenovo HA VM .122:8123"]
    caddy --> storage["Ryzen .120: Immich, Jellyfin, FileBrowser, qBittorrent"]
    applications -->|NFS media| nas["Ryzen NAS /mnt/nas"]
    storage --> nas
    dockerbackup[".121: one Restic instance"] --> repo["Ryzen shared Restic repository"]
    storagebackup[".120: one Restic instance"] --> repo
```

`stacks/storage/` and `stacks/docker/` are deployment boundaries. Each child retains its own Compose project name, container names, network and application data paths. One Beszel agent per Docker host is sufficient. No retired Chromebox is required.

The root `.env` remains the primary configuration source; `make config` renders stack environments and `make config-check` verifies them. Caddy uses `STORAGE_HOST`, `DOCKER_HOST` and independently `HA_HOST`. Home Assistant retains its existing reverse-proxy route; configure trusted proxies on that VM for the Lenovo proxy address as needed.

Persistent application state is under `/opt/homelab/data`. Media is on Ryzen and shared by NFS; downloads and media paths are preserved. Backups include application state on both Docker hosts, selected NAS data, Caddy named volumes and Unbound state. See [coverage and consistency limits](backups.md). The shared backup disk is not an off-site backup.

Before changing production paths, follow [migration and rollback](migration.md). A Git move neither migrates a running container nor changes its existing mounts.
