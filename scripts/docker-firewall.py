#!/usr/bin/env python3
"""Install an opt-in DOCKER-USER policy without replacing Docker/UFW rules."""
import argparse
import ipaddress
import json
from pathlib import Path
import subprocess


def rules(settings, version):
    sources = [str(ipaddress.ip_network(s, strict=False)) for s in settings['allowed_sources']
               if ipaddress.ip_network(s, strict=False).version == version]
    chain = 'HOMELAB-DOCKER'
    # Declare and explicitly flush only our chain inside the same transaction.
    # --noflush preserves the rest of the table, not this replacement policy.
    lines = ['*filter', f':{chain} - [0:0]', f'-F {chain}',
             f'-A {chain} -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN',
             f'-A {chain} -i docker0 -j RETURN', f'-A {chain} -i br+ -j RETURN',
             f'-A {chain} -i tailscale0 -j RETURN']
    lines += [f'-A {chain} -s {source} -j RETURN' for source in sources]
    for protocol in ('tcp', 'udp'):
        for port in settings.get('public_' + protocol, []):
            if not isinstance(port, int) or not 1 <= port <= 65535:
                raise ValueError('Public ports must be integers from 1 to 65535')
            lines.append(f'-A {chain} -p {protocol} -m conntrack --ctstate DNAT --ctorigdstport {port} -j RETURN')
    # Restrict ingress to Docker's default bridge naming only; leave unrelated
    # forwarding (e.g. a Tailscale subnet router) untouched.
    lines += [f'-A {chain} -o docker0 -j DROP', f'-A {chain} -o br+ -j DROP',
              f'-A {chain} -j RETURN', 'COMMIT']
    return '\n'.join(lines) + '\n'


def install(settings):
    # Render/validate both address families before changing either one.
    policies = {v: rules(settings, v) for v in (4, 6)}
    for version, executable in [(4, 'iptables'), (6, 'ip6tables')]:
        present = subprocess.run([executable, '-w', '-S', 'DOCKER-USER'], capture_output=True).returncode == 0
        if not present:
            if version == 4:
                raise RuntimeError('DOCKER-USER missing: this policy requires Docker iptables backend, not native nftables')
            print('No IPv6 DOCKER-USER chain; no IPv6 bridge policy installed. Host/proxy traffic still requires UFW.')
            continue
        subprocess.run([executable + '-restore', '--wait', '--noflush', '--test'], input=policies[version], text=True, check=True)
        subprocess.run([executable + '-restore', '--wait', '--noflush'], input=policies[version], text=True, check=True)
        jump = ['DOCKER-USER', '-j', 'HOMELAB-DOCKER']
        if subprocess.run([executable, '-w', '-C', *jump], capture_output=True).returncode:
            subprocess.run([executable, '-w', '-I', *jump], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('--preview', action='store_true')
    args = parser.parse_args()
    settings = json.loads(args.config.read_text())
    if args.preview:
        for version in (4, 6):
            print(f'# IPv{version}\n' + rules(settings, version))
    else:
        install(settings)
