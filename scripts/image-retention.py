#!/usr/bin/env python3
"""Remove only previously observed homelab images unused for at least 14 days."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
RETENTION = 14 * 86400


def output(*args):
    return subprocess.check_output(['docker', *args], text=True, timeout=60).strip()


def inventory(node):
    ids = output('ps', '-aq').split()
    containers = json.loads(output('inspect', *ids)) if ids else []
    used = {c['Image'] for c in containers}
    managed = {c['Image'] for c in containers
               if c.get('Config', {}).get('Labels', {}).get('homelab.node') == node}
    return used, managed


def reconcile(state, used, managed, now, cleanup=False, remove=None):
    for ident in managed:
        state[ident] = None
    for ident in list(state):
        if ident in used:
            state[ident] = None
        elif state[ident] is None:
            state[ident] = now
        elif cleanup and now - state[ident] >= RETENTION:
            if remove(ident) is not False:
                del state[ident]
    return state


def run(node, cleanup=False):
    directory = ROOT / '.deploy-state' / node
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'images.json'
    state = json.loads(path.read_text()) if path.exists() else {}
    used, managed = inventory(node)
    def remove(ident):
        # No --force: Docker refuses removal if another container now uses it.
        existing = set(output('image', 'ls', '-q', '--no-trunc').split())
        if ident in existing:
            result = subprocess.run(['docker', 'image', 'rm', ident], timeout=60,
                                    capture_output=True, text=True)
            if result.returncode:
                # A new user/container/tag can race the inventory. Never force
                # removal or rerun a successful deployment because of it.
                print(f'Retained {ident}: Docker refused non-forced removal')
                return False
            print(f'Removed expired homelab image {ident}')
        return True
    reconcile(state, used, managed, time.time(), cleanup, remove)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state) + '\n')
    temporary.chmod(0o600)
    os.replace(temporary, path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('node', choices=['apps', 'storage', 'infra'])
    parser.add_argument('--cleanup', action='store_true')
    args = parser.parse_args()
    run(args.node, args.cleanup)
