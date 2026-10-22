"""Assert effective automerge policy after all matching repository rules."""
import fnmatch
import json
from pathlib import Path
import unittest

CONFIG = json.loads((Path(__file__).resolve().parents[1] / 'renovate.json').read_text())


def automerge(package, filename, update_type, manager='docker-compose'):
    dependency = {'matchPackageNames': package, 'matchFileNames': filename,
                  'matchUpdateTypes': update_type, 'matchDatasources': 'docker',
                  'matchManagers': manager}
    result = CONFIG['automerge']
    for rule in CONFIG['packageRules']:
        # This evaluator covers the selectors used by this repository; fail if
        # policy evolves beyond those, rather than silently ignore a matcher.
        for key in rule:
            if key.startswith('match') and key not in dependency:
                raise AssertionError('Add coverage for matcher: ' + key)
        if all(any(fnmatch.fnmatchcase(dependency[key], pattern) for pattern in rule[key])
               for key in dependency if key in rule):
            result = rule.get('automerge', result)
    return result


class RenovatePolicyTests(unittest.TestCase):
    def test_review_only_images_override_all_catch_all_rules(self):
        for package, filename, manager in [
            ('caddy', 'stacks/infra/caddy/Dockerfile', 'custom.regex'),
            ('mazzolino/restic', 'stacks/apps/restic/compose.yaml', 'docker-compose'),
            ('portainer/portainer-ee', 'stacks/infra/portainer/compose.yaml', 'docker-compose'),
            ('portainer/agent', 'ansible/group_vars/all.yml', 'custom.regex'),
            ('ghcr.io/immich-app/postgres', 'stacks/storage/immich/compose.yaml', 'docker-compose'),
            ('docker.io/valkey/valkey', 'stacks/storage/immich/compose.yaml', 'docker-compose'),
        ]:
            for update in ('major', 'minor', 'patch', 'digest', 'pin'):
                with self.subTest(package=package, update=update):
                    self.assertFalse(automerge(package, filename, update, manager))

    def test_regular_app_minor_patch_policy_is_preserved(self):
        for update in ('minor', 'patch'):
            self.assertTrue(automerge('lscr.io/linuxserver/sonarr', 'stacks/apps/sonarr/compose.yaml', update))
        for update in ('major', 'digest', 'pin'):
            self.assertFalse(automerge('lscr.io/linuxserver/sonarr', 'stacks/apps/sonarr/compose.yaml', update))
