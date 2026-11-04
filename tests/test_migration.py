"""Migration identity, backup coverage and fail-closed scheduler regression tests."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MigrationTests(unittest.TestCase):
    def manifest(self, node, stack):
        result = subprocess.run(['docker', 'compose', '--env-file', '.env.example',
                                 'config', '--format', 'json'],
                                cwd=ROOT / 'stacks' / node / stack,
                                capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def test_two_targets_and_two_backup_instances(self):
        targets = {p.name for p in (ROOT / 'stacks').iterdir() if p.is_dir() and not p.name.startswith('_')}
        self.assertEqual(targets, {'storage', 'docker'})
        for node in targets:
            manifest = self.manifest(node, 'restic')
            self.assertEqual(set(manifest['services']), {'restic'})
            self.assertEqual(manifest['services']['restic']['hostname'], node)
            self.assertEqual(manifest['name'], 'restic')
        self.assertFalse((ROOT / 'stacks/docker/homeassistant').exists())
        self.assertFalse(list((ROOT / 'stacks').glob('*/diun')))

    def test_named_volumes_reference_existing_production_identity(self):
        manifest = self.manifest('docker', 'restic')
        sources = {v['source'] for v in manifest['services']['restic']['volumes'] if v['type'] == 'volume'}
        self.assertEqual(sources, {'caddy-data', 'caddy-config', 'unbound-state'})
        for key, name in [('caddy-data', 'caddy_caddy-data'), ('caddy-config', 'caddy_caddy-config'),
                          ('unbound-state', 'pihole-unbound_unbound-state')]:
            self.assertTrue(manifest['volumes'][key]['external'])
            self.assertEqual(manifest['volumes'][key]['name'], name)
        for mount in manifest['services']['restic']['volumes']:
            if mount['target'] != '/repo':
                self.assertTrue(mount['read_only'])

    def test_home_assistant_route_is_independent(self):
        route = (ROOT / 'stacks/docker/caddy/Caddyfile').read_text()
        self.assertIn('has.{$DOMAIN}', route)
        self.assertIn('reverse_proxy {$HA_HOST}:8123', route)
        manifest = self.manifest('docker', 'caddy')
        self.assertEqual(manifest['services']['caddy']['environment']['HA_HOST'], '192.168.1.122')

    def test_scheduler_only_backs_up_existing_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            log = directory / 'calls'
            stub = directory / 'restic'
            stub.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALLS"\n'
                            'if [ "$1" = snapshots ]; then exit "${SNAPSHOT_STATUS:-0}"; fi\n')
            stub.chmod(0o755)
            for node in ('docker', 'storage'):
                env = dict(os.environ, PATH=tmp + ':' + os.environ['PATH'], CALLS=str(log),
                           RESTIC_BACKUP_TIME='03:00', BACKUP_HOST=node)
                result = subprocess.run(['sh', str(ROOT / 'scripts/restic-scheduler.sh'), '--once'], env=env)
                self.assertEqual(result.returncode, 0)
                calls = log.read_text().splitlines()
                self.assertEqual(calls[0], 'snapshots --json')
                self.assertTrue(calls[1].startswith('backup --host ' + node))
                self.assertEqual(len(calls), 2)
                log.unlink()
                result = subprocess.run(['sh', str(ROOT / 'scripts/restic-scheduler.sh'), '--once'],
                                        env=dict(env, SNAPSHOT_STATUS='1'))
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(log.read_text().splitlines(), ['snapshots --json'])
                log.unlink()
