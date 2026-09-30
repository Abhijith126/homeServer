# Clone once, bootstrap each node

On a Debian 12+ or Ubuntu 24.04+ machine with systemd, Git, a normal sudo user, and network access:

```bash
git clone https://github.com/Abhijith126/homeServer.git ~/homeServer
cd ~/homeServer
./scripts/bootstrap-node.sh
```

The script asks which node this machine is: storage, apps, or infra. You can pass the role explicitly:

| Machine | Command |
| --- | --- |
| Storage / ryzen | ./scripts/bootstrap-node.sh storage |
| Applications | ./scripts/bootstrap-node.sh apps |
| Infrastructure | ./scripts/bootstrap-node.sh infra |

Run storage first so its NFS exports are ready before setting up the clients. Keep the checkout owned by the user running the script. Run without sudo; the script requests sudo for system changes.

## What setup handles

- Installs prerequisites and Ansible in a local virtual environment.
- Uses the current login user and OS, rather than the checked-in personal inventory.
- Asks for the three LAN addresses, subnet, local data paths, and storage export/mount paths.
- Installs standard Docker Engine and Compose, log rotation, firewall rules, and shared networks.
- Sets up NFS exports on storage and persistent NFS mounts on apps/infra.
- Creates application data/media directories and node aliases in /etc/hosts.
- Configures Pi-hole's local domain route and Caddy's upstream addresses.
- Offers internal TLS or Cloudflare DNS-01, with a token prompt when Cloudflare is selected.
- Generates initial application passwords/encryption keys where appropriate, preserves configured secrets, and asks for the shared backup password and external credentials.
- Generates per-stack environment files, installs the deployment timer, and performs the first deployment.

The timer then pulls main about every five minutes, deploys that node's stacks, and prunes unused images after successful startup checks. See [automation.md](automation.md) for policy, logs, retries, and cleanup details.

## Values you provide once

Use consistent LAN addresses, export directories, and media UID/GID across all three runs. The backup password must be identical on every node.

The wizard offers qBittorrent/VPN, Diun/SMTP, Beszel agent, and backups where those stacks exist. Services whose external credentials are unavailable can be skipped, and enabled later by rerunning the same command. Other stacks can be skipped by name. Portfolio prompts for the repository publishing the standalone ZIP and checksum, so a fork can use its own application.

Secrets and generated settings stay in the ignored root .env, .bootstrap directory, and infra-only cloudflare.env. They are not written to inventory.ini or committed. The temporary Tailscale auth-key file is removed when setup exits. For already configured services, setup reuses credentials from the root .env or existing stack .env files. If existing Immich or Homarr data is detected without its credential, it asks for the current password/key instead of generating a replacement. Rerunning setup preserves configured passwords and encryption keys.

Initial generated credentials can be read from the node's root .env. App-specific first-run account creation, adding indexers/download-client connections, and logging in to external providers remain application administration.

## Storage and network prerequisites

Have the OS installed and your LAN addresses assigned or reserved before running setup. Provide directories on the disks you intend to use; bootstrap creates missing directories and exports/mounts them, but does not partition disks, format filesystems, or migrate existing application data.

Do not point new services at existing production data without checking the paths and versions. Snap Docker is detected and left alone; migrate its data to standard Docker before using this bootstrap on that machine.

Once infra is running, point clients/router DNS at its LAN address to use Pi-hole and the local service names. For internal TLS, trust Caddy's local CA on client devices. For Cloudflare certificates, provide a suitable public domain and API token. Router DHCP settings, public DNS records, and provider accounts require access to those external systems.

The currently published portfolio ZIP targets amd64; other hardware needs a matching application build or can skip that stack.

## Share or fork

Someone else can fork this repository, clone their fork on each machine, and run the same script. The wizard supplies their usernames, addresses, paths, domain, and credentials. Git polling follows the checkout's origin remote; it does not force deployments back to Abhijith126's repository.

Install the hosted Renovate app on the fork to receive that fork's image-update PRs. No deployment token or inbound GitHub connection to the nodes is needed. For a private fork, configure non-interactive read access for the deployment user.

## Rerun, recover, and maintain

Run the same bootstrap command to change configuration or enable skipped integrations. Setup pauses an existing deployment timer and waits for any active deployment to finish before writing configuration. A provisioning failure leaves the timer paused until setup is rerun successfully.

View deployment output:

```bash
journalctl -u homelab-deploy.service -f
systemctl list-timers homelab-deploy.timer
```

The local Ansible entry point is ansible/bootstrap.yml; its inventory and variables are generated under .bootstrap. The original ansible/site.yml remains available for advanced remote provisioning.
