#!/usr/bin/env python3
"""Preserve a working live Unbound anchor before adding its persistent volume."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile

TARGET = '/var/lib/unbound'


def docker(stack, *args):
    return subprocess.check_output(['docker', *args], cwd=stack, text=True,
                                   stderr=subprocess.DEVNULL, timeout=60).strip()


def prepare(stack):
    config = json.loads(docker(stack, 'compose', 'config', '--format', 'json'))
    volume = next((v for v in config['services']['pihole'].get('volumes', [])
                   if v.get('type') == 'volume' and v.get('target') == TARGET), None)
    if volume is None:
        raise RuntimeError('Pi-hole has no Unbound state volume in its configuration.')
    source = volume['source']
    definition = config.get('volumes', {}).get(source, {})
    name = definition.get('name') or (source if definition.get('external')
                                     else config['name'] + '_' + source)
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]*', name):
        raise RuntimeError('Invalid Unbound volume name.')
    container = docker(stack, 'compose', 'ps', '--all', '--quiet', 'pihole')
    if not container:
        print('Pi-hole: fresh deployment; the startup hook will bootstrap verified anchors.')
        return
    mounts = json.loads(docker(stack, 'inspect', '--format', '{{json .Mounts}}', container))
    if any(m.get('Type') == 'volume' and m.get('Name') == name
           and m.get('Destination') == TARGET for m in mounts):
        print('Pi-hole: Unbound state is already persisted.')
        return
    consumers = docker(stack, 'ps', '-aq', '--filter', 'volume=' + name).split()
    if consumers:
        raise RuntimeError('Unbound volume is used by another container; refusing to overwrite it.')
    answer = docker(stack, 'exec', container, 'dig', '@127.0.0.1', '-p', '5335', '.',
                    'DNSKEY', '+dnssec', '+time=3', '+tries=1')
    if 'status: NOERROR' not in answer or not re.search(r'^;; flags:.*\bad(?:\s|;)', answer, re.M):
        raise RuntimeError('Existing Unbound cannot validate DNSSEC; repair it before migrating its state.')
    image = docker(stack, 'inspect', '--format', '{{.Image}}', container)
    helper = None
    with tempfile.TemporaryDirectory(prefix='homelab-unbound-') as tmp:
        anchor = Path(tmp) / 'root.key'
        docker(stack, 'cp', container + ':' + TARGET + '/root.key', str(anchor))
        if not anchor.is_file() or anchor.stat().st_size == 0:
            raise RuntimeError('Live root.key is empty; refusing to recreate Pi-hole.')
        try:
            # The image ID already exists locally. No pull, DNS, or helper startup.
            docker(stack, 'volume', 'create', '--label', 'com.docker.compose.project=' + config['name'],
                   '--label', 'com.docker.compose.volume=' + source, name)
            helper = docker(stack, 'create', '--network', 'none', '--entrypoint', '/bin/true',
                            '--mount', 'type=volume,src=' + name + ',dst=' + TARGET + ',volume-nocopy', image)
            docker(stack, 'cp', str(anchor), helper + ':' + TARGET + '/root.key')
            # Verify bytes were actually written into the mounted volume.
            copied = Path(tmp) / 'check.key'
            docker(stack, 'cp', helper + ':' + TARGET + '/root.key', str(copied))
            if copied.read_bytes() != anchor.read_bytes():
                raise RuntimeError('Unbound anchor copy verification failed; update cancelled.')
        finally:
            if helper:
                docker(stack, 'rm', helper)
    print('Pi-hole: live trust anchor copied and verified in ' + name + '.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stack', type=Path)
    args = parser.parse_args()
    try:
        prepare(args.stack.resolve())
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        # Subprocess stderr is suppressed to avoid including environment details.
        parser.exit(1, 'Pi-hole state preparation refused: ' + str(error) + '\n')
