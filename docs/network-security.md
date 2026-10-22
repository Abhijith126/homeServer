# Network policy rollout

UFW alone does not filter Docker-published bridge ports. The Docker role includes
an **opt-in** DOCKER-USER policy for Docker's iptables backend (including
iptables-nft). Native Docker nftables is not supported; a missing IPv4
DOCKER-USER chain causes installation to fail.

Review trusted source networks and intentionally public ports before enabling:

```yaml
docker_firewall_enabled: true
docker_allowed_sources: ["192.168.1.0/24"]
docker_public_tcp: [80, 443]  # Only on a node intended to serve public HTTP/HTTPS.
docker_public_udp: [443]     # Optional public HTTP/3.
```

Defaults allow LAN, tailscale0, container-originated and established traffic;
other ingress to docker0/br-* bridges is blocked. Custom bridge names need an
explicit policy extension. Host networking and userland-proxy listeners still
need UFW rules. IPv6 bridge rules require an IPv6 DOCKER-USER chain; if absent,
the installer reports that no IPv6 bridge policy was installed.

Provisioning applies the policy and installs a Docker startup hook to reapply it
after reboot/restart. It rebuilds only its own chain and adds its DOCKER-USER jump;
other firewall rules are preserved. Hook failure causes Docker's systemd start
to fail, rather than silently claiming filtering is active.

Keep a second SSH/console session open during rollout. From LAN and Tailscale,
test DNS, Caddy, NFS, apps and container/VPN egress. From an untrusted network,
verify that admin/app ports are blocked and only configured public ports work.
Repeat over IPv6 and after reboot. Unit tests check generated policy, not the
behavior of your actual router, VLANs or firewall.

Setting the variable false does not remove an installed policy. To disable it,
remove /etc/systemd/system/docker.service.d/homelab-firewall.conf, reload systemd,
and remove the DOCKER-USER jump to HOMELAB-DOCKER in each installed address family.
Do not flush DOCKER-USER or Docker's own chains.

NFS defaults now export only to the apps/infra IPs, not the entire LAN. Update
nfs_exports when those addresses change. Bootstrap generates them from configured
addresses; existing saved bootstrap profiles need reconfiguration to update.
no_root_squash remains explicit for root-run backups and existing ownership.
Moving to root_squash requires testing backup reads/writes and ownership first.
