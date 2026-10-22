"""Failure injection and disposable recovery checks; never access live data."""
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


backup = module('stack-backup')
restore = module('restic-restore')
health = module('health-audit')
retention = module('image-retention')
firewall = module('docker-firewall')
policy = module('stack-policy')


class BackupSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.stack = self.root / 'stacks/example'
        self.stack.mkdir(parents=True)
        (self.root / 'data/example').mkdir(parents=True)
        (self.root / 'data/example/config').write_text('recover me')
        (self.stack / '.env').write_text(f'DOCKER_DATA={self.root}/data\nNFS_BACKUP={self.root}/backup\n')

    def test_success_archive_is_private_and_restorable(self):
        archive = backup.backup(self.stack)
        self.assertEqual(archive.stat().st_mode & 0o777, 0o600)
        destination = self.root / 'restored'
        destination.mkdir()
        subprocess.run(['tar', '-xzf', str(archive), '-C', str(destination)], check=True)
        self.assertEqual((destination / 'example/config').read_text(), 'recover me')

    def test_failed_tar_restarts_only_previously_running_containers(self):
        calls = []
        def run(args, **kwargs):
            calls.append(args)
            if args[0] == 'tar':
                raise subprocess.CalledProcessError(1, args)
        with patch.object(backup.subprocess, 'check_output', return_value='running-id\n'), \
                patch.object(backup.subprocess, 'run', side_effect=run):
            with self.assertRaises(subprocess.CalledProcessError):
                backup.backup(self.stack, stop=True)
        self.assertEqual(calls[-1], ['docker', 'start', 'running-id'])
        self.assertEqual(list((self.root / 'backup/example').iterdir()), [])

    def test_partial_stop_failure_still_attempts_restart(self):
        with patch.object(backup.subprocess, 'check_output', return_value='one two'), \
                patch.object(backup.subprocess, 'run', side_effect=[subprocess.CalledProcessError(1, 'stop'), None]) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                backup.backup(self.stack, stop=True)
        self.assertEqual(run.call_args.args[0], ['docker', 'start', 'one', 'two'])

    def test_wrapper_paths_and_template_remain_valid(self):
        for wrapper in (ROOT / 'stacks').glob('*/*/backup.sh'):
            if wrapper.parent.name != 'immich':
                self.assertIn('scripts/stack-backup.py', wrapper.read_text())


class RestoreTests(unittest.TestCase):
    def test_explicit_snapshot_validates_host_tag_and_ambiguity(self):
        snapshots = [
            {'id': 'a' * 64, 'hostname': 'apps', 'tags': ['homelab'], 'time': '2026-01-01T00:00:00Z'},
            {'id': 'b' * 64, 'hostname': 'infra', 'tags': ['homelab'], 'time': '2026-01-02T00:00:00Z'},
            {'id': 'c' * 64, 'hostname': 'storage', 'tags': ['media'], 'time': '2026-01-03T00:00:00Z'},
        ]
        self.assertEqual(restore.select_snapshot(snapshots, 'apps', 'homelab', 'aaaaaaaa'), 'a' * 64)
        self.assertEqual(restore.select_snapshot(snapshots, 'apps', 'homelab', 'latest'), 'a' * 64)
        for ident in ['bbbbbbbb', 'cccccccc', 'dddddddd']:
            with self.assertRaises(ValueError):
                restore.select_snapshot(snapshots, 'apps', 'homelab', ident)
        with self.assertRaises(ValueError):
            restore.select_snapshot(snapshots, 'storage', 'homelab', 'cccccccc')
        with self.assertRaises(ValueError):
            restore.select_snapshot(snapshots + [dict(snapshots[0], id='a' * 63 + 'b')], 'apps', 'homelab', 'aaaaaaaa')

    def test_wrong_snapshot_is_rejected_before_creating_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'new'
            listing = json.dumps([{'id': 'b' * 64, 'hostname': 'infra', 'tags': ['homelab']}])
            with patch.object(restore.subprocess, 'check_output', return_value=listing), \
                    patch.object(restore.subprocess, 'run') as run:
                with self.assertRaises(ValueError):
                    restore.restore('apps', 'homelab', 'bbbbbbbb', target, execute=True)
                run.assert_not_called()
            self.assertFalse(target.exists())

    def test_plan_requires_new_target_and_explicit_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                restore.command('apps', 'homelab', 'latest', Path(tmp))
            command = restore.command('apps', 'homelab', 'latest', Path(tmp) / 'new')
            self.assertEqual(command[command.index('--host') + 1], 'apps')
            self.assertIn('--verify', command)
            with patch.object(restore.subprocess, 'run') as run:
                restore.restore('apps', 'homelab', 'latest', Path(tmp) / 'new')
                run.assert_not_called()
            self.assertFalse((Path(tmp) / 'new').exists())

    def test_media_only_belongs_to_storage(self):
        with self.assertRaises(ValueError):
            restore.command('apps', 'media', 'latest', Path('/unused-target'))

    @unittest.skipUnless(shutil.which('restic'), 'restic binary required for disposable restore drill')
    def test_real_restic_restore_selects_correct_host_and_verifies_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = dict(os.environ, RESTIC_REPOSITORY=str(root / 'repo'), RESTIC_PASSWORD='disposable-test-only')
            def restic(*args):
                return subprocess.run(['restic', *args], env=env, check=True, capture_output=True, text=True)
            restic('init')
            data = root / 'data'
            data.mkdir()
            sample = data / 'config'
            sample.write_text('apps backup')
            restic('backup', '--host', 'apps', '--tag', 'homelab', str(data))
            sample.write_text('wrong node')
            restic('backup', '--host', 'infra', '--tag', 'homelab', str(data))
            snapshots = json.loads(restic('snapshots', '--json').stdout)
            wrong = next(s['id'] for s in snapshots if s['hostname'] == 'infra')
            with self.assertRaises(ValueError):
                restore.select_snapshot(snapshots, 'apps', 'homelab', wrong)
            selected = restore.select_snapshot(snapshots, 'apps', 'homelab', 'latest')
            target = root / 'restored'
            command = restore.command('apps', 'homelab', selected, target)
            args = command[command.index('restore'):]
            args[args.index('--target') + 1] = str(target)
            restic(*args)
            self.assertEqual((target / sample.relative_to('/')).read_text(), 'apps backup')


class HealthTests(unittest.TestCase):
    def test_unconfigured_agent_is_not_a_health_incident(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stack = root / 'stacks/apps/beszel-agent'
            stack.mkdir(parents=True)
            (stack / 'compose.yaml').write_text('fixture')
            with patch.object(health, 'ROOT', root), patch.object(health, 'compose') as compose:
                self.assertEqual(health.audit('apps', set()), [])
                compose.assert_not_called()

    def test_lock_defers_check_but_cached_staleness_still_alerts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now = datetime.now(timezone.utc)
            with patch.object(health, 'ROOT', root), patch.object(health, 'compose') as compose:
                compose.return_value = json.dumps([{'time': now.isoformat()}])
                self.assertIsNone(health.backup_freshness(root, 'restic', 'apps', 'homelab', 120))
                compose.side_effect = subprocess.CalledProcessError(11, 'restic')
                self.assertIsNone(health.backup_freshness(root, 'restic', 'apps', 'homelab', 120))
                cache = root / '.deploy-state/apps/backup-homelab.json'
                cache.write_text(json.dumps({'snapshots': [{'time': (now - timedelta(hours=121)).isoformat()}]}))
                self.assertIn('no successful snapshot', health.backup_freshness(root, 'restic', 'apps', 'homelab', 120))

    def test_initial_lock_is_deferred_but_persistent_lock_and_other_errors_are_not_hidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(health, 'ROOT', root), patch.object(health, 'compose') as compose:
                compose.side_effect = subprocess.CalledProcessError(11, 'restic')
                self.assertIsNone(health.backup_freshness(root, 'restic', 'apps', 'homelab', 120))
                cache = root / '.deploy-state/apps/backup-homelab.json'
                cache.write_text(json.dumps({'deferred_since': (datetime.now(timezone.utc) - timedelta(hours=121)).isoformat()}))
                self.assertIn('repository locked', health.backup_freshness(root, 'restic', 'apps', 'homelab', 120))
                compose.side_effect = subprocess.CalledProcessError(1, 'restic')
                with self.assertRaises(subprocess.CalledProcessError):
                    health.backup_freshness(root, 'restic', 'apps', 'homelab', 120)

    def test_missing_stopped_unhealthy_and_scaled_services_are_detected(self):
        services = {'db': {}, 'web': {'deploy': {'replicas': 2}}}
        failures = health.service_failures(services, [{'Service': 'db', 'State': 'running', 'Health': 'unhealthy'},
            {'Service': 'web', 'State': 'running', 'Health': 'healthy'}])
        self.assertEqual(len(failures), 2)
        self.assertTrue(health.service_failures({'db': {}}, []))
        self.assertTrue(health.service_failures({'db': {}}, [{'Service': 'db', 'State': 'exited'}]))
        self.assertFalse(health.service_failures({'db': {}}, [{'Service': 'db', 'State': 'running', 'Health': ''}]))

    def test_backup_freshness_empty_stale_future_and_current(self):
        now = datetime.now(timezone.utc)
        for hours, expected in [(0, True), (119, True), (121, False), (-1, False)]:
            self.assertEqual(health.fresh([{'time': (now - timedelta(hours=hours)).isoformat()}], now, 120), expected)
        self.assertFalse(health.fresh([], now, 120))

    def test_compose_json_array_and_json_lines(self):
        self.assertEqual(health.rows('[{"Service":"web"}]'), health.rows('{"Service":"web"}\n'))

    def test_audit_checks_backup_even_when_service_is_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stack = root / 'stacks/apps/restic'
            stack.mkdir(parents=True)
            (stack / 'compose.yaml').write_text('fixture')
            def compose(directory, *args):
                if args[0] == 'config':
                    return json.dumps({'services': {'restic': {}}})
                if args[0] == 'ps':
                    return json.dumps([{'Service': 'restic', 'State': 'running'}])
                self.assertIn('--host', args)
                self.assertIn('apps', args)
                return '[]'
            with patch.object(health, 'ROOT', root), patch.object(health, 'compose', side_effect=compose):
                self.assertIn('no successful snapshot', health.audit('apps', set())[0])
                self.assertEqual(health.audit('apps', {'restic'}), [])

    def test_audit_reports_docker_errors_without_exposing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stack = root / 'stacks/apps/web'
            stack.mkdir(parents=True)
            (stack / 'compose.yaml').write_text('fixture')
            error = subprocess.CalledProcessError(1, 'docker', output='secret')
            with patch.object(health, 'ROOT', root), patch.object(health, 'compose', side_effect=error):
                failures = health.audit('apps', set())
            self.assertEqual(len(failures), 1)
            self.assertNotIn('secret', failures[0])


class RetentionTests(unittest.TestCase):
    def test_agent_labels_enter_managed_inventory(self):
        for node in ('apps', 'storage', 'infra'):
            containers = [{'Image': 'agent-image', 'Config': {'Labels': {'homelab.node': node}}}]
            with patch.object(retention, 'output', side_effect=['agent-container', json.dumps(containers)]):
                used, managed = retention.inventory(node)
            self.assertIn('agent-image', managed)

    def test_age_is_since_disuse_not_image_creation(self):
        removed = []
        state = retention.reconcile({}, {'old'}, {'old'}, 0)
        retention.reconcile(state, {'new'}, {'new'}, 100, True, removed.append)
        retention.reconcile(state, {'new'}, {'new'}, 100 + retention.RETENTION - 1, True, removed.append)
        self.assertEqual(removed, [])
        retention.reconcile(state, {'new'}, {'new'}, 100 + retention.RETENTION, True, removed.append)
        self.assertEqual(removed, ['old'])
        self.assertNotIn('unrelated', state)

    def test_used_images_reset_clock_and_record_only_never_removes(self):
        state = {'old': 0}
        removed = []
        retention.reconcile(state, set(), set(), retention.RETENTION * 2, False, removed.append)
        self.assertEqual(removed, [])
        retention.reconcile(state, {'old'}, set(), retention.RETENTION * 2, True, removed.append)
        self.assertIsNone(state['old'])

    def test_refused_removal_keeps_retention_record(self):
        state = {'old': 0}
        retention.reconcile(state, set(), set(), retention.RETENTION, True, lambda ident: False)
        self.assertEqual(state, {'old': 0})


class FirewallTests(unittest.TestCase):
    def test_families_and_public_original_ports(self):
        settings = {'allowed_sources': ['192.168.1.0/24', 'fd00::/64'], 'public_tcp': [443]}
        v4, v6 = firewall.rules(settings, 4), firewall.rules(settings, 6)
        self.assertIn('192.168.1.0/24', v4)
        self.assertNotIn('fd00::', v4)
        self.assertIn('fd00::/64', v6)
        self.assertIn('--ctorigdstport 443', v4)
        self.assertIn('-i tailscale0 -j RETURN', v4)
        self.assertIn('-o br+ -j DROP', v4)
        self.assertEqual([line for line in v4.splitlines() if line.startswith('-F')], ['-F HOMELAB-DOCKER'])
        self.assertLess(v4.index('-F HOMELAB-DOCKER'), v4.index('-A HOMELAB-DOCKER'))

    def test_invalid_sources_and_ports_are_rejected(self):
        for settings in [{'allowed_sources': ['invalid']}, {'allowed_sources': [], 'public_tcp': ['443;bad']}]:
            with self.assertRaises(ValueError):
                firewall.rules(settings, 4)


class StackPolicyTests(unittest.TestCase):
    def test_missing_empty_placeholder_quoted_keys_and_explicit_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for content in ['', 'BESZEL_AGENT_KEY=', 'BESZEL_AGENT_KEY=CHANGEME', "BESZEL_AGENT_KEY='CHANGEME'"]:
                (root / '.env').write_text(content)
                self.assertIn('beszel-agent', policy.effective_skip(root, {'portainer'}))
            (root / '.env').write_text("BESZEL_AGENT_KEY='ssh-ed25519 example-public-key'")
            self.assertEqual(policy.effective_skip(root, {'portainer'}), {'portainer'})
            self.assertIn('beszel-agent', policy.effective_skip(root, {'beszel-agent'}))


if __name__ == '__main__':
    unittest.main()
