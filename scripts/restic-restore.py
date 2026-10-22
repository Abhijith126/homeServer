#!/usr/bin/env python3
"""Restore to a NEW staging directory, never over live application data."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def command(node, kind, snapshot, target):
    if node not in ('apps', 'storage', 'infra') or kind not in ('homelab', 'media'):
        raise ValueError('Invalid node or snapshot kind')
    if kind == 'media' and node != 'storage':
        raise ValueError('Media snapshots belong to storage')
    if snapshot != 'latest' and not re.fullmatch(r'[0-9a-fA-F]{8,64}', snapshot):
        raise ValueError('Use latest or a hexadecimal snapshot ID (at least 8 characters), without a subpath')
    target = Path(target)
    if not target.is_absolute() or target.exists() or target.is_symlink():
        raise ValueError('Destination must be an absolute, non-existing staging directory')
    if ',' in str(target) or ':' in str(target):
        raise ValueError('Destination must not contain Docker mount separators')
    service = 'restic-media' if kind == 'media' else 'restic'
    return ['docker', 'compose', 'run', '--rm', '--no-deps', '--entrypoint', 'restic',
            '--volume', str(target) + ':/restore', service, 'restore', snapshot,
            '--host', node, '--tag', kind, '--target', '/restore', '--verify']


def select_snapshot(snapshots, node, kind, requested):
    if requested == 'latest':
        candidates = [s for s in snapshots if s.get('hostname') == node and kind in (s.get('tags') or [])]
        if not candidates:
            raise ValueError('No snapshot matches the requested host and tag')
        selected = max(candidates, key=lambda s: datetime.fromisoformat(s['time'].replace('Z', '+00:00')))
    else:
        candidates = [s for s in snapshots if s['id'].startswith(requested.lower())]
        if len(candidates) != 1:
            raise ValueError('Snapshot ID is missing or ambiguous')
        selected = candidates[0]
        if selected.get('hostname') != node or kind not in (selected.get('tags') or []):
            raise ValueError('Snapshot does not belong to the requested host and tag')
    return selected['id']


def restore(node, kind, snapshot, target, execute=False):
    args = command(node, kind, snapshot, target)
    print(shlex.join(args))
    if not execute:
        print('Preview only; snapshot metadata is validated on execution. Add --execute to restore into the new staging directory.')
        return
    service = 'restic-media' if kind == 'media' else 'restic'
    # Listing is read-only and does not mount/create the restore destination.
    # Restic ignores host/tag filters for explicit IDs, so validate ourselves
    # and pass an unambiguous full ID even for latest.
    listing = subprocess.check_output(['docker', 'compose', 'run', '--rm', '--no-deps',
        '--entrypoint', 'restic', service, 'snapshots', '--json'],
        cwd=ROOT / 'stacks' / node / 'restic', text=True, timeout=120)
    resolved = select_snapshot(json.loads(listing) or [], node, kind, snapshot)
    args = command(node, kind, resolved, target)
    print(f'Validated snapshot {resolved} for {node}/{kind}')
    target.mkdir(mode=0o700, parents=False, exist_ok=False)
    subprocess.run(args, cwd=ROOT / 'stacks' / node / 'restic', check=True)
    print(f'Restored and verified in {target}. Stop affected apps before copying selected data into place.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('node', choices=['apps', 'storage', 'infra'])
    parser.add_argument('kind', choices=['homelab', 'media'])
    parser.add_argument('target', type=Path)
    parser.add_argument('--snapshot', default='latest')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    restore(args.node, args.kind, args.snapshot, args.target, args.execute)
