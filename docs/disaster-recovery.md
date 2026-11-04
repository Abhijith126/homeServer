# Disaster recovery

See [backup coverage, consistency and retention](backups.md) before relying on a snapshot. Restore Ryzen first, then Lenovo Docker and its NFS mounts; restore the Home Assistant VM through its separate Proxmox/HA backup process.

Use `scripts/restic-restore.py HOST homelab /absolute/new/staging --snapshot ID` to preview; add `--execute` to restore and verify. `HOST` may be `docker`, `storage`, or historical `apps`/`infra`. Historical hosts use the current Docker Restic Compose configuration and preserve host filtering. Media uses `storage media` with the same single Storage Restic service. The destination must not already exist.

Never restore over live databases. Validate exports in an isolated instance, stop affected writers in an approved maintenance window, then selectively copy verified state. Restore named-volume contents to the existing identified volume, not an inferred new project volume. See [migration rollback](migration.md).
