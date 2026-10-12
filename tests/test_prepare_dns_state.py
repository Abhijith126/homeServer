"""Model first-rollout state migration without Docker or external connectivity."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepare_dns', ROOT / 'scripts/prepare-dns-state.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class StateMigrationTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.container = 'live'
        self.mounts = []
        self.answer = ';; ->>HEADER<<- status: NOERROR, id: 1\n;; flags: qr rd ra ad; QUERY: 1'
        self.anchor = b'verified live trust anchor\n'
        self.saved = None
        self.fail_copy = False
        self.configuration = {'name': 'pihole-unbound', 'services': {'pihole': {'volumes': [
            {'type': 'volume', 'source': 'unbound-state', 'target': '/var/lib/unbound'}]}},
            'volumes': {'unbound-state': {'name': 'pihole-unbound_unbound-state'}}}

    def docker(self, stack, *args):
        self.calls.append(args)
        if args[:3] == ('compose', 'config', '--format'):
            return json.dumps(self.configuration)
        if args[:2] == ('compose', 'ps'):
            return self.container
        if args[0] == 'inspect':
            return json.dumps(self.mounts) if '.Mounts' in args[2] else 'sha256:local-image'
        if args[0] == 'exec':
            return self.answer
        if args[0] == 'create':
            return 'helper'
        if args[0] == 'cp':
            source, destination = args[1:]
            if source.startswith('live:'):
                Path(destination).write_bytes(self.anchor)
            elif destination.startswith('helper:'):
                if self.fail_copy:
                    raise subprocess.CalledProcessError(1, ['docker', *args])
                self.saved = Path(source).read_bytes()
            else:
                Path(destination).write_bytes(self.saved)
        return ''

    def prepare(self):
        with patch.object(module, 'docker', side_effect=self.docker):
            module.prepare(ROOT)

    def test_first_rollout_seeds_verified_live_key_using_local_stopped_helper(self):
        self.prepare()
        self.assertEqual(self.saved, self.anchor)
        create = next(c for c in self.calls if c[0] == 'create')
        self.assertIn('none', create)
        self.assertIn('type=volume,src=pihole-unbound_unbound-state,dst=/var/lib/unbound,volume-nocopy', create)
        self.assertEqual(create[-1], 'sha256:local-image')
        self.assertIn(('rm', 'helper'), self.calls)
        self.assertTrue(any(c[:2] == ('volume', 'create') and 'com.docker.compose.volume=unbound-state' in c for c in self.calls))
        self.assertFalse(any(c[0] in ('pull', 'start', 'stop') for c in self.calls))

    def test_existing_managed_state_is_not_overwritten(self):
        self.mounts = [{'Type': 'volume', 'Name': 'pihole-unbound_unbound-state', 'Destination': '/var/lib/unbound'}]
        self.prepare()
        self.assertIsNone(self.saved)
        self.assertFalse(any(c[0] == 'create' for c in self.calls))

    def test_broken_live_validation_blocks_recreation_preparation(self):
        self.answer = ';; ->>HEADER<<- status: SERVFAIL\n;; flags: qr rd ra;'
        with self.assertRaises(RuntimeError):
            self.prepare()
        self.assertFalse(any(c[0] == 'create' for c in self.calls))

    def test_copy_failure_aborts_and_removes_only_temporary_helper(self):
        self.fail_copy = True
        with self.assertRaises(subprocess.CalledProcessError):
            self.prepare()
        self.assertIn(('rm', 'helper'), self.calls)
        self.assertFalse(any(c[0] == 'volume' and c[1] == 'rm' for c in self.calls))

    def test_fresh_install_uses_authenticated_startup_bootstrap(self):
        self.container = ''
        self.prepare()
        self.assertFalse(any(c[0] == 'create' for c in self.calls))


if __name__ == '__main__':
    unittest.main()
