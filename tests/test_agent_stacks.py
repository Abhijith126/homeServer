"""Verify per-node agent discovery, version alignment, and restart policies."""
import json
import re
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


def compose_command():
    if shutil.which('docker'):
        result = subprocess.run(['docker', 'compose', 'version'], capture_output=True)
        if result.returncode == 0:
            return ['docker', 'compose']
    if shutil.which('docker-compose'):
        return ['docker-compose']
    return None


class AgentStackTests(unittest.TestCase):
    def test_agent_is_discoverable_on_each_node_and_versions_match(self):
        canonical = ROOT / 'stacks/infra/beszel-agent'
        for node in ('apps', 'storage', 'infra'):
            with self.subTest(node=node):
                directory = ROOT / 'stacks' / node / 'beszel-agent'
                self.assertIn(directory / 'compose.yaml',
                              list((ROOT / 'stacks' / node).glob('*/compose.yaml')))
                for filename in ('compose.yaml', '.env.example'):
                    actual = (directory / filename).read_text()
                    expected = (canonical / filename).read_text()
                    if filename == 'compose.yaml':
                        self.assertIn(f'homelab.node: "{node}"', actual)
                        actual = actual.replace(f'homelab.node: "{node}"', 'homelab.node: "infra"')
                    self.assertEqual(actual, expected)

    def test_all_rendered_services_restart_automatically(self):
        command = compose_command()
        if command is None:
            self.skipTest('Docker Compose is required to inspect resolved service policies')
        for path in sorted((ROOT / 'stacks').glob('*/*/compose.yaml')):
            if path.parent.parent.name == '_template':
                continue
            with self.subTest(stack=str(path.relative_to(ROOT))):
                result = subprocess.run(command + ['--env-file', '.env.example',
                                                  'config', '--format', 'json'],
                                        cwd=path.parent, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                for name, service in json.loads(result.stdout)['services'].items():
                    self.assertEqual(service.get('restart'), 'unless-stopped',
                                     f'{path}: {name} must restart automatically')
                if path.parent.name == 'caddy':
                    service = json.loads(result.stdout)['services']['caddy']
                    version = re.search(r'^ARG CADDY_VERSION=(.+)$',
                                        (path.parent / 'Dockerfile').read_text(), re.M).group(1)
                    self.assertEqual(service['build']['args']['CADDY_VERSION'], version)
                    self.assertEqual(service['image'], 'caddy-cloudflare:' + version)
