# Hardware

| Physical server | Workloads |
| --- | --- |
| Ryzen (192.168.1.120) | NAS/HDD storage and Storage Docker deployment |
| Lenovo (Proxmox) | Docker VM 192.168.1.121 and Home Assistant VM 192.168.1.122 |

Ryzen retains `/mnt/nas` for media, `/mnt/hdd2/restic` for the shared encrypted repository, and `/opt/homelab/data` for application state. Lenovo Docker uses `/opt/homelab/data`, mounts Ryzen media at `/mnt/nas`, and mounts backups at `/mnt/nfs/backup`.

The retired Chromeboxes are not deployment targets. Keep backups independent of the media disks and maintain an off-site copy. Hardware acceleration on Ryzen remains opt-in in Jellyfin's Compose configuration.
