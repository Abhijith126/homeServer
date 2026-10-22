#!/usr/bin/env python3
"""Read-only service and backup freshness audit; never restart stateful apps."""
import argparse
from datetime import datetime, timezone
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('stack_policy', ROOT / 'scripts/stack-policy.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


def compose(stack, *args):
    return subprocess.check_output(['docker', 'compose', *args], cwd=stack,
                                   text=True, stderr=subprocess.DEVNULL, timeout=90)


def rows(raw):
    raw = raw.strip()
    if not raw:
        return []
    if raw.startswith('['):
        return json.loads(raw)
    return [json.loads(line) for line in raw.splitlines()]


def service_failures(services, containers):
    failures = []
    for name, settings in services.items():
        if settings.get('profiles'):
            continue
        expected = settings.get('deploy', {}).get('replicas', settings.get('scale', 1))
        matches = [c for c in containers if c.get('Service') == name]
        healthy = [c for c in matches if c.get('State') == 'running' and c.get('Health', '') in ('', 'healthy')]
        if len(healthy) < expected:
            failures.append(f'{name}: {len(healthy)}/{expected} running and healthy')
    return failures


def fresh(snapshots, now, max_hours):
    times = [datetime.fromisoformat(s['time'].replace('Z', '+00:00')) for s in snapshots]
    return bool(times) and 0 <= (now - max(times)).total_seconds() <= max_hours * 3600


def backup_freshness(stack, service, node, tag, max_hours):
    now = datetime.now(timezone.utc)
    path = ROOT / '.deploy-state' / node / f'backup-{tag}.json'
    cached = json.loads(path.read_text()) if path.exists() else {}
    try:
        snapshots = json.loads(compose(stack, 'exec', '-T', service, 'restic',
            'snapshots', '--json', '--host', node, '--tag', tag)) or []
        cached = {'snapshots': [{'time': s['time']} for s in snapshots]}
    except subprocess.CalledProcessError as error:
        if error.returncode != 11:
            raise
        print(f'DEFER restic/{tag}: repository locked; recheck next tick using last-known freshness')
        cached.setdefault('deferred_since', now.isoformat())
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(cached) + '\n')
    temporary.chmod(0o600)
    os.replace(temporary, path)
    if 'snapshots' in cached:
        if not fresh(cached['snapshots'], now, max_hours):
            return f'restic/{tag}: no successful snapshot within {max_hours:g} hours'
    elif (now - datetime.fromisoformat(cached['deferred_since'])).total_seconds() > max_hours * 3600:
        return f'restic/{tag}: repository locked without a successful freshness check for {max_hours:g} hours'
    return None


def audit(node, skip, max_hours=120):
    skip = policy.effective_skip(ROOT, skip)
    failures = []
    for manifest in sorted((ROOT / 'stacks' / node).glob('*/compose.yaml')):
        stack = manifest.parent
        if stack.name in skip:
            continue
        try:
            services = json.loads(compose(stack, 'config', '--format', 'json'))['services']
            failures.extend(f'{stack.name}/{item}' for item in service_failures(
                services, rows(compose(stack, 'ps', '--all', '--format', 'json'))))
            if stack.name == 'restic':
                for service, tag in [('restic', 'homelab'), ('restic-media', 'media')]:
                    if service not in services:
                        continue
                    failure = backup_freshness(stack, service, node, tag, max_hours)
                    if failure:
                        failures.append(failure)
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            failures.append(f'{stack.name}: audit unavailable (check Compose configuration, Docker and backup access)')
    if not list((ROOT / 'stacks' / node).glob('*/compose.yaml')):
        failures.append('No stack manifests found')
    return failures


def notify(node, failures, directory):
    path = directory / 'health.json'
    previous = json.loads(path.read_text()) if path.exists() else {}
    state = {'failures': failures, 'checked': datetime.now(timezone.utc).isoformat(),
             'notification': 'quiet'}
    changed = previous.get('failures', []) != failures
    retry = previous.get('notification') in ('failed', 'not configured') and bool(failures)
    if changed or retry:
        spec = importlib.util.spec_from_file_location('deploy_report', ROOT / 'scripts/deploy-report.py')
        report = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(report)
        try:
            settings = report.config.read_env(ROOT / '.env')
            state['notification'] = report.send(settings, f'[homeServer][{node}] ' +
                ('Health alert' if failures else 'Health recovered'),
                '\n'.join(failures) if failures else 'All configured service and backup freshness checks passed.')
        except Exception:
            state['notification'] = 'failed'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, indent=2) + '\n')
    temporary.chmod(0o600)
    os.replace(temporary, path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('node', choices=['apps', 'storage', 'infra'])
    parser.add_argument('--skip', default=os.environ.get('HOMELAB_SKIP_STACKS', 'portainer'))
    parser.add_argument('--max-backup-hours', type=float, default=float(os.environ.get('HOMELAB_BACKUP_MAX_HOURS', '120')))
    parser.add_argument('--notify', action='store_true')
    args = parser.parse_args()
    if args.max_backup_hours <= 0:
        parser.error('--max-backup-hours must be positive')
    directory = ROOT / '.deploy-state' / args.node
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Deployment or audit in progress; check on the next timer tick.')
            raise SystemExit(0)
        failures = audit(args.node, set(args.skip.split()), args.max_backup_hours)
        if args.notify:
            notify(args.node, failures, directory)
        print('\n'.join(failures) if failures else 'No failures detected; any deferred freshness checks are logged above.')
        raise SystemExit(bool(failures))
