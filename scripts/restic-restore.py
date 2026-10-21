#!/usr/bin/env python3
"""Restore to a NEW staging directory, never over live application data."""
import argparse
from pathlib import Path
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def command(node, kind, snapshot, target):
    if node not in ('apps', 'storage', 'infra') or kind not in ('homelab', 'media'):
        raise ValueError('Invalid node or snapshot kind')
    if kind == 'media' and node != 'storage':
        raise ValueError('Media snapshots belong to storage')
    if not snapshot or snapshot.startswith('-') or ':' in snapshot:
        raise ValueError('Use latest or an explicit snapshot ID, without a subpath')
    target = Path(target)
    if not target.is_absolute() or target.exists() or target.is_symlink():
        raise ValueError('Destination must be an absolute, non-existing staging directory')
    if ',' in str(target) or ':' in str(target):
        raise ValueError('Destination must not contain Docker mount separators')
    service = 'restic-media' if kind == 'media' else 'restic'
    return ['docker', 'compose', 'run', '--rm', '--no-deps', '--entrypoint', 'restic',
            '--volume', str(target) + ':/restore', service, 'restore', snapshot,
            '--host', node, '--tag', kind, '--target', '/restore', '--verify']


def restore(node, kind, snapshot, target, execute=False):
    args = command(node, kind, snapshot, target)
    print(shlex.join(args))
    if not execute:
        print('Preview only. Add --execute to restore into the new staging directory.')
        return
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
