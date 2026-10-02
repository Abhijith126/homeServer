"""Exercise calendar semantics, saved settings, and database dump failures."""
import gzip
import importlib.util
import io
import json
from pathlib import Path
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


schedule = module('deploy-schedule')
backup = module('immich-backup')
config = module('bootstrap-config')


class ScheduleTests(unittest.TestCase):
    def test_calendar_expressions_are_valid_systemd_calendars(self):
        for cadence in ('hourly', 'daily', 'weekly', 'monthly'):
            rendered = schedule.timer(cadence)
            expression = next(line.split('=', 1)[1] for line in rendered.splitlines() if line.startswith('OnCalendar='))
            subprocess.run(['systemd-analyze', 'calendar', expression], check=True, capture_output=True)
            self.assertIn('Persistent=true', rendered)
        self.assertIn('Mon *-*-* 03:00:00', schedule.timer('weekly'))
        self.assertIn('*-*-01 03:00:00', schedule.timer('monthly'))
        self.assertIn('OnUnitInactiveSec=5min', schedule.timer('5min'))

    def test_invalid_values_rejected(self):
        for args in [('never',), ('daily', '25:00'), ('daily', '03:00', 'Unknown/Zone')]:
            with self.assertRaises(ValueError):
                schedule.timer(*args)

    def test_schedule_only_preserves_profile_and_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.bootstrap').mkdir()
            path = root / '.bootstrap/vars.json'
            profile = {'bootstrap_node': 'apps', 'bootstrap_skip': ['portainer'], 'credential': 'unchanged'}
            path.write_text(json.dumps(profile))
            (root / '.env').write_text('SECRET=unchanged\n')
            config.configure_updates(root=root, schedule='monthly', update_time='04:15')
            updated = json.loads(path.read_text())
            for key, value in profile.items():
                self.assertEqual(updated[key], value)
            self.assertEqual(updated['bootstrap_update_schedule'], 'monthly')
            self.assertEqual((root / '.env').read_text(), 'SECRET=unchanged\n')


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.running = 'container'
        self.existing = 'container'
        self.data = self.root / 'postgres'
        self.services = {'database': {'environment': {'POSTGRES_USER': 'postgres'},
                         'volumes': [{'type': 'bind', 'source': str(self.data), 'target': '/var/lib/postgresql/data'}]},
                         'immich-server': {'environment': {'NFS_BACKUP': str(self.root)}}}

    def compose(self, args, **kwargs):
        if 'config' in args:
            return json.dumps({'services': self.services})
        return self.existing if '--all' in args else self.running

    def test_first_deployment_skips_backup_but_existing_data_blocks(self):
        self.running = self.existing = ''
        with patch.object(backup.subprocess, 'check_output', side_effect=self.compose):
            backup.backup(self.root, True)
            self.data.mkdir()
            (self.data / 'PG_VERSION').write_text('16')
            with self.assertRaises(RuntimeError):
                backup.backup(self.root, True)

    def test_failure_removes_partial_dump_and_keeps_previous_archive(self):
        self.dump_test(1)

    def test_success_creates_readable_private_archive(self):
        self.dump_test(0)

    def dump_test(self, exit_code):
        destination = self.root / 'immich'
        destination.mkdir()
        old = destination / 'immich-db-20200101-000000.sql.gz'
        old.write_bytes(b'previous')
        with patch.object(backup.subprocess, 'check_output', side_effect=self.compose), \
                patch.object(backup.subprocess, 'Popen') as popen:
            process = popen.return_value.__enter__.return_value
            process.stdout = io.BytesIO(b'SQL dump\n')
            process.wait.return_value = exit_code
            if exit_code:
                with self.assertRaises(RuntimeError):
                    backup.backup(self.root, True)
                self.assertEqual(list(destination.iterdir()), [old])
            else:
                backup.backup(self.root, True)
                new = next(p for p in destination.iterdir() if p != old)
                self.assertEqual(gzip.decompress(new.read_bytes()), b'SQL dump\n')
                self.assertEqual(new.stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main()
